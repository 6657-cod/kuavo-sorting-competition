# 第一阶段真实测试记录

记录日期：2026年10月10日。下表时间为 Asia/Shanghai（UTC+8）；原始 JUnit 时间来自机器 UTC，Humble pytest 6.2.5 报告的 timestamp 不带时区。

本次改动基于仓库提交 `2c48ebf1b0d13336b4769b83efe0921d16bc927c`，在未提交的工作区源码上实际执行。对应程序、Launch、测试及构建脚本的校验值保存在 [source-sha256.txt](source-sha256.txt)，可在仓库根目录执行 `sha256sum -c docs/test-results/source-sha256.txt` 检查是否仍为同一版本。

## 执行环境与结果

| 执行 | 开始时间（UTC+8） | 结果 | 耗时 | 退出码 |
| --- | --- | --- | --- | --- |
| Debian 云宿主 Python 3.12.14 / pytest 9.1.1 | 13:12:12 | 48通过，ROS模块1跳过 | 0.091秒 | 0 |
| Ubuntu容器 Python 3.10.12 / ROS 2 Humble，直接pytest | 13:15:13 | 56通过，0失败、0错误、0跳过 | 17.598秒 | 0 |
| 同一Humble容器，colcon test | 13:15:32 | 56通过，0失败、0错误、0跳过 | 17.827秒 | 0 |

48项为普通 Python 状态机/模拟模型测试，8项为ROS集成用例。直接pytest与colcon test执行的是同一套56项测试，两次运行不能算成112个不同用例。宿主机没有ROS，其跳过结果**不构成ROS实测**。

Humble验证实际使用官方 `ros:humble-ros-base` Docker镜像，Ubuntu **22.04.5 LTS**，x86_64；镜像拉取摘要：

```text
ros@sha256:860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19
```

已安装版本（实际查询）：

```text
python3-colcon-core  0.21.3+upstream-1
ros-humble-rclpy     3.3.22-1jammy.20260907.213431
ros-humble-launch-ros 0.19.14-1jammy.20260907.214826
ros-humble-std-msgs  4.9.2-1jammy.20260907.205027
```

本次ROS验证使用真实rclpy、DDS、launch与独立节点进程，没有mock ROS模块。容器在云端Docker中运行，**不是VMware本地实测、实体机器人实测或真实抓取**。未安装大型三维仿真软件。

## 实际命令与原始证据

宿主机命令（venv中安装pytest后）：

```bash
/workspace/kuavo-cloud/test-venv/bin/python -m pytest -q \
  --junitxml=/workspace/kuavo-cloud/python-tests.xml
```

最终完整Humble流程（容器的工作目录为仓库根目录）：

```bash
docker exec kuavo-humble-dev bash -lc \
  'KUAVO_TEST_WORKSPACE=/workspace/kuavo-cloud/humble bash scripts/test_humble.sh'
```

脚本实际执行构建、source安装空间、pytest、colcon test和colcon test-result。构建成功：1个包；最终test-result为 `56 tests, 0 errors, 0 failures, 0 skipped`。采集日志时保留底层命令退出码。

- [Humble完整执行日志](humble-validation.log)
- [Humble直接pytest JUnit](humble-pytest.junit.xml)
- [Humble colcon JUnit](humble-colcon.junit.xml)
- [无ROS宿主pytest JUnit](python-host.junit.xml)

实际调试中，首次运行测试脚本因 `set -u` 与Humble生成的环境脚本不兼容而失败：`AMENT_TRACE_SETUP_FILES: unbound variable`。已修正为保留 `set -e` 与 `pipefail`，然后完整重跑成功。表中Humble结果为修正后最终运行，未把首次失败当作通过。

## 覆盖范围与限制

普通Python用例验证五类各两件、10件完成、重复start、未知控制、停止重启、重复与过期反馈、识别/动作阶段超时及重试耗尽、失败重试、重试预算归零、严格整数/布尔值/有限坐标校验、无效JSON、模拟取消、动作去重与成功反馈重放、忙状态、同一操作内容变更拒绝。

8项ROS用例实际验证：

1. 三节点经DDS完成五类各两件的模拟分拣。
2. 每件首次识别超时后重试恢复，共10次重试。
3. 每件首次动作失败后重试恢复，共10次重试。
4. 识别超时重试耗尽，进入error且完成数为0。
5. 动作失败重试耗尽，进入error且完成数为0。
6. 运行中重复start、stop、重新start、注入旧任务成功反馈，新任务仍正确完成。
7. CLI确认与退出码：start成功0、busy为1、stop成功0、非法动作2。
8. 无调度节点时CLI返回1并报告发现失败。

GitHub Actions配置已添加，但本次没有在GitHub触发或验证其运行，也没有推送或合并。真实机器人、官方SDK、真实视觉、物理碰撞/安全、网络跨机器通信和节点崩溃后的持久化去重尚未验证。软件stop只取消模拟动作，不可作实体机器人急停使用。
