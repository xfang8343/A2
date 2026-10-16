# P1 机型胸部中间交互相机

## 修改 ROS2 后端方法

在 P1 机型上 /aima/hal/camera/interactive/color 默认以 iceoryx 后端进行发布，调用较为麻烦，现提供修改其发布后端增加 ros2 后端的方法（1.2/1.0 版本通过 iceoryx 的方式调用仍保留兼容，新版本推荐修改后通过标准 ROS2 接口进行订阅），注意新增 ros2 后端后 tz_camera 模块会有 14% 的 CPU 占用率上升。

P1 机型新增 ROS2 后端方法：

1. 在 ORIN 上首先备份对应配置文件

    ```bash
    cp /agibot/software/v0/config/tzcamera/tzcamera_config.yaml /agibot/software/v0/config/tzcamera.tzcamera_config.yaml.original
    ```

2. 然后修改该文件，将其 aimrt.channel.pub_topic_options 中的 /aima/hal/camera/interactive/color 的 enable_backends 中添加一项 ros2，从 [iceoryx] 变为 [iceoryx, ros2]

    ```yaml
    aimrt:
      channel:
        pub_topic_options:
          - topic_name: "/aima/hal/camera/interactive/color"
            enable_backends: [iceoryx, ros2]
    ```

3. 重启机器人

## 原方法调用说明

Iceoryx 后端为共享内存通信，因此只能在 ORIN 上运行，示例依赖于 aimrt_py 库，因此需要在 ORIN 上安装 aimrt_py 库，安装方法如下：

```bash
pip install aimrt_py-1.0.0-cp310-cp310-linux_aarch64.whl
```

安装完成后，可以运行 start_interactive_camera.sh 脚本启动示例：

```bash
./start_interactive_camera.sh
```
