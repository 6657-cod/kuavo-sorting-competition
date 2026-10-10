#!/usr/bin/env bash
# Build and test the actual Humble package. Outputs stay outside the checkout.
# Humble's generated setup scripts read unset variables; keep error/pipe checks.
set -eo pipefail
source /opt/ros/humble/setup.bash
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
artifact_root=${KUAVO_TEST_WORKSPACE:-/tmp/kuavo-sorting-humble-tests}
mkdir -p "$artifact_root"
cd "$repository"
python3 -c 'import rclpy, launch_ros, pytest'
colcon --log-base "$artifact_root/log" build --base-paths "$repository" \
    --build-base "$artifact_root/build" --install-base "$artifact_root/install" \
    --executor sequential
source "$artifact_root/install/setup.bash"
python3 -m pytest -q --junitxml="$artifact_root/pytest.xml"
colcon --log-base "$artifact_root/log" test --base-paths "$repository" \
    --build-base "$artifact_root/build" --install-base "$artifact_root/install" \
    --packages-select kuavo_sorting --event-handlers console_direct+ \
    --return-code-on-test-failure
colcon test-result --test-result-base "$artifact_root/build" --verbose
