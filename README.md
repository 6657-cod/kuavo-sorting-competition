# Kuavo 竞赛第一阶段：ROS 2 模拟分拣

目标环境：**Ubuntu 22.04、ROS 2 Humble、Python 3.10**。五类零件各两件，共 10 件；本工程只模拟识别和动作，不连接相机、夹爪或 Kuavo 实体机器人，也没有 Kuavo 官方 SDK 接口。

| 类别 | 模拟收纳位置 | 数量 |
| --- | --- | --- |
| 尼龙水管件 | A | 2 |
| 螺丝刀 | B | 2 |
| 插座模块 | C | 2 |
| 膨胀螺栓 | D | 2 |
| 线缆 | E | 2 |

## Ubuntu 22.04 / Humble 构建

以下假定已经按 ROS 官方说明安装 ROS 2 Humble 并配置 apt 源。命令不安装三维仿真软件。

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-pytest \
  ros-humble-rclpy ros-humble-std-msgs ros-humble-launch-ros
source /opt/ros/humble/setup.bash
mkdir -p ~/kuavo_ws/src
cd ~/kuavo_ws/src
git clone https://github.com/6657-cod/kuavo-sorting-competition.git
cd ~/kuavo_ws
colcon build --packages-select kuavo_sorting --symlink-install
source install/setup.bash
```

已有 checkout 时直接使用它，不要再次 clone。当前云端改动须先检查并合并，GitHub 上的旧版本不会自动包含这些改动。VMware 无需 GPU；同一虚拟机的各终端须使用相同的 `ROS_DOMAIN_ID`。

## 运行

终端 1：

```bash
source /opt/ros/humble/setup.bash
source ~/kuavo_ws/install/setup.bash
ros2 launch kuavo_sorting sorting.launch.py
```

终端 2：

```bash
source /opt/ros/humble/setup.bash
source ~/kuavo_ws/install/setup.bash
ros2 run kuavo_sorting task_client start
ros2 topic echo /sorting/status std_msgs/msg/String \
  --qos-durability transient_local --qos-reliability reliable
```

最终状态应为 `finished`，`completed=10`，`counts` 中五类均为 2，`simulated=true`。客户端成功退出只说明调度节点接受了指令，**不代表整轮任务已经完成**。再次发送 `start` 会从第 0 件开始新一轮；运行中重复 `start` 返回 `busy`。

另一个已 source 的终端可停止：

```bash
ros2 run kuavo_sorting task_client stop
```

停止会取消尚未完成的模拟动作并保留当前计数；再次开始会清零。停止后的旧消息由任务与请求标识过滤。此控制不是实体机器人的急停。关闭 launch 用 Ctrl+C。

可检查节点发现：

```bash
ros2 node list --no-daemon --spin-time 3
ros2 pkg executables kuavo_sorting
```

应有 `vision_node`、`robot_node`、`sorting_node` 三个节点，以及四个可执行入口（含 `task_client`）。

## 参数与故障注入

| Launch 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `timeout_seconds` | 5.0 | 每次识别或动作响应的等待上限，正有限秒数 |
| `max_retries` | 2 | 每件的识别阶段和动作阶段各自最多重试次数；0 表示不重试 |
| `action_seconds` | 0.7 | 模拟动作耗时，正有限秒数 |
| `drop_first_attempts` | 0 | 每件识别阶段丢弃前 N 次响应，用于模拟超时 |
| `fail_first_attempts` | 0 | 每件动作阶段前 N 次已执行尝试返回模拟失败 |

```bash
# 识别首次超时、动作首次失败，均应恢复并完成10件
ros2 launch kuavo_sorting sorting.launch.py \
  timeout_seconds:=1.0 action_seconds:=0.1 \
  drop_first_attempts:=1 fail_first_attempts:=1
# 另一个终端发送 start，观察 retrying 和最终 finished
```

```bash
# 识别一直丢失，1次重试后应 error，completed=0
ros2 launch kuavo_sorting sorting.launch.py \
  timeout_seconds:=0.5 max_retries:=1 drop_first_attempts:=10
```

修改参数后重启 launch，避免同时运行两套同名节点。机器人忙、反馈无效或 `success=false` 会触发有上限的阶段重试；耗尽后进入 `error` 并取消当前模拟动作。错误信息保留出错的等待阶段。

## 自动化测试

无 ROS 的机器只运行逻辑测试：

```bash
python3 -m pip install pytest
python3 -m pytest -q test/test_state_machine.py
```

这验证普通 Python 状态机与模拟模型，不构成 ROS 实测。

Ubuntu / Humble 运行完整验证（包括真实 ROS 进程、DDS 话题通信、Launch、CLI 退出码）：

```bash
cd ~/kuavo_ws/src/kuavo-sorting-competition
bash scripts/test_humble.sh
```

脚本在 `/tmp/kuavo-sorting-humble-tests` 构建，不依赖先前 workspace；保存 JUnit、构建和测试日志，并检查 pytest 与 colcon 的失败退出码。可设置 `KUAVO_TEST_WORKSPACE` 改输出目录。完整测试需要已安装 `rclpy`、`launch_ros`、`pytest`、`colcon`。无 ROS 时集成模块会跳过，不能据此声称 ROS 验证通过。

使用已有构建也可运行：

```bash
cd ~/kuavo_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
python3 -m pytest -q src/kuavo-sorting-competition/test
colcon test --packages-select kuavo_sorting --return-code-on-test-failure
colcon test-result --verbose
```

集成测试使用域 176，缺服务测试使用域 177，并设置 `ROS_LOCALHOST_ONLY=1`；测试运行时不要在这两个域启动其他节点。测试创建、关闭自己的 launch 进程，不需要实体机器人。新增 GitHub Actions 工作流会在 push/PR 后执行 Humble 测试并上传日志；本次云端执行与未来 GitHub Actions 执行是两件事。

工程分析见 [docs/architecture.md](docs/architecture.md)，实际执行证据见 [docs/test-results/README.md](docs/test-results/README.md)。
