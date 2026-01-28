# LEGO Factory v3 - ROS2 Humble with noVNC
# ========================================
# Browser-based visualization for RViz2, Gazebo, and ROS2 tools
#
# Based on ROS2 Humble (Ubuntu 22.04) - stable LTS
# Includes: RViz2, Gazebo, MoveIt2, noVNC

FROM osrf/ros:humble-desktop

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1
ENV VNC_PORT=5901
ENV NOVNC_PORT=6080
ENV RESOLUTION=1920x1080

# Install VNC and desktop dependencies (noVNC installed from GitHub for newer version)
RUN apt-get update && apt-get install -y \
    tigervnc-standalone-server \
    tigervnc-common \
    websockify \
    supervisor \
    openbox \
    xterm \
    x11-xserver-utils \
    dbus-x11 \
    fonts-dejavu \
    python3-pip \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install newer noVNC from GitHub (apt version is too old)
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /opt/novnc && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Install ROS2 packages for LEGO Factory
RUN apt-get update && apt-get install -y \
    ros-humble-rviz2 \
    ros-humble-rqt* \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-moveit \
    ros-humble-moveit-visual-tools \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-rosbridge-suite \
    ros-humble-joint-state-publisher-gui \
    ros-humble-robot-state-publisher \
    ros-humble-xacro \
    ros-humble-tf2-tools \
    && rm -rf /var/lib/apt/lists/*

# Install additional visualization tools
RUN apt-get update && apt-get install -y \
    ros-humble-plotjuggler-ros \
    ros-humble-foxglove-bridge \
    && rm -rf /var/lib/apt/lists/* || true

# Create VNC password (default: lego)
RUN mkdir -p /root/.vnc && \
    echo "lego" | vncpasswd -f > /root/.vnc/passwd && \
    chmod 600 /root/.vnc/passwd


# Configure VNC startup
RUN echo '#!/bin/bash\n\
[ -r /root/.Xresources ] && xrdb /root/.Xresources\n\
openbox-session &\n\
' > /root/.vnc/xstartup && chmod +x /root/.vnc/xstartup

# Install tint2 panel for easier navigation
RUN apt-get update && apt-get install -y tint2 pcmanfm && rm -rf /var/lib/apt/lists/*

# Configure openbox for ROS2 tools
RUN mkdir -p /root/.config/openbox && \
    echo '<?xml version="1.0" encoding="UTF-8"?>\n\
<openbox_config xmlns="http://openbox.org/3.4/rc">\n\
  <applications>\n\
    <application class="*">\n\
      <decor>yes</decor>\n\
    </application>\n\
  </applications>\n\
</openbox_config>' > /root/.config/openbox/rc.xml

# Create openbox right-click menu with ROS2 tools
RUN echo '<?xml version="1.0" encoding="UTF-8"?>\n\
<openbox_menu xmlns="http://openbox.org/3.4/menu">\n\
  <menu id="root-menu" label="LEGO Factory ROS2">\n\
    <separator label="ROS2 Visualization"/>\n\
    <item label="RViz2"><action name="Execute"><command>/usr/local/bin/launch-rviz</command></action></item>\n\
    <item label="rqt"><action name="Execute"><command>/usr/local/bin/launch-rqt</command></action></item>\n\
    <item label="rqt_graph"><action name="Execute"><command>/usr/local/bin/launch-rqt-graph</command></action></item>\n\
    <item label="rqt_console"><action name="Execute"><command>/usr/local/bin/launch-rqt-console</command></action></item>\n\
    <item label="rqt_topic"><action name="Execute"><command>/usr/local/bin/launch-rqt-topic</command></action></item>\n\
    <item label="rqt_tf_tree"><action name="Execute"><command>/usr/local/bin/launch-rqt-tf-tree</command></action></item>\n\
    <item label="PlotJuggler"><action name="Execute"><command>/usr/local/bin/launch-plotjuggler</command></action></item>\n\
    <separator label="Simulation"/>\n\
    <item label="Gazebo"><action name="Execute"><command>/usr/local/bin/launch-gazebo</command></action></item>\n\
    <separator label="Terminal"/>\n\
    <item label="XTerm"><action name="Execute"><command>xterm -fa "DejaVu Sans Mono" -fs 11</command></action></item>\n\
    <item label="File Manager"><action name="Execute"><command>pcmanfm</command></action></item>\n\
    <separator/>\n\
    <item label="Exit"><action name="Exit"/></item>\n\
  </menu>\n\
</openbox_menu>' > /root/.config/openbox/menu.xml

# Create autostart for tint2 panel
RUN mkdir -p /root/.config/openbox && \
    echo '#!/bin/bash\n\
tint2 &\n\
' > /root/.config/openbox/autostart && chmod +x /root/.config/openbox/autostart

# Configure tint2 panel
RUN mkdir -p /root/.config/tint2 && echo '\n\
# Tint2 config for ROS2 noVNC\n\
panel_position = top center horizontal\n\
panel_size = 100% 32\n\
panel_background_id = 1\n\
taskbar_mode = single_desktop\n\
taskbar_padding = 2 2 2\n\
task_text = 1\n\
task_icon = 1\n\
task_centered = 1\n\
task_maximum_size = 200 32\n\
task_padding = 4 2 4\n\
task_font = DejaVu Sans 10\n\
task_font_color = #ffffff 100\n\
task_background_id = 0\n\
task_active_background_id = 2\n\
launcher_padding = 4 4 4\n\
launcher_background_id = 0\n\
launcher_icon_size = 24\n\
launcher_item_app = /usr/local/share/applications/rviz2.desktop\n\
launcher_item_app = /usr/local/share/applications/rqt.desktop\n\
launcher_item_app = /usr/local/share/applications/rqt-graph.desktop\n\
launcher_item_app = /usr/local/share/applications/xterm.desktop\n\
clock_format = %H:%M\n\
background_color = #2c3e50 90\n\
border_width = 0\n\
background_color_hover = #34495e 100\n\
background_color_pressed = #1a252f 100\n\
' > /root/.config/tint2/tint2rc

# Create desktop entries for launcher
RUN mkdir -p /usr/local/share/applications && \
    echo '[Desktop Entry]\nName=RViz2\nExec=/usr/local/bin/launch-rviz\nIcon=rviz\nType=Application\nCategories=ROS2;' > /usr/local/share/applications/rviz2.desktop && \
    echo '[Desktop Entry]\nName=rqt\nExec=/usr/local/bin/launch-rqt\nIcon=rqt\nType=Application\nCategories=ROS2;' > /usr/local/share/applications/rqt.desktop && \
    echo '[Desktop Entry]\nName=rqt_graph\nExec=/usr/local/bin/launch-rqt-graph\nIcon=rqt\nType=Application\nCategories=ROS2;' > /usr/local/share/applications/rqt-graph.desktop && \
    echo '[Desktop Entry]\nName=XTerm\nExec=xterm -fa "DejaVu Sans Mono" -fs 11\nIcon=utilities-terminal\nType=Application\nCategories=System;' > /usr/local/share/applications/xterm.desktop

# Create ROS2 workspace for LEGO Factory
RUN mkdir -p /ros2_ws/src

# Create supervisor configuration
RUN mkdir -p /var/log/supervisor && echo '[supervisord]\n\
nodaemon=true\n\
logfile=/var/log/supervisor/supervisord.log\n\
pidfile=/var/run/supervisord.pid\n\
\n\
[program:xvnc]\n\
command=/usr/bin/Xvnc :1 -geometry %(ENV_RESOLUTION)s -depth 24 -rfbauth /root/.vnc/passwd -rfbport %(ENV_VNC_PORT)s -SecurityTypes VncAuth,TLSVnc\n\
autorestart=true\n\
priority=10\n\
stdout_logfile=/var/log/supervisor/xvnc.log\n\
stderr_logfile=/var/log/supervisor/xvnc_err.log\n\
\n\
[program:openbox]\n\
command=/usr/bin/openbox-session\n\
environment=DISPLAY=":1"\n\
autorestart=true\n\
priority=15\n\
stdout_logfile=/var/log/supervisor/openbox.log\n\
stderr_logfile=/var/log/supervisor/openbox_err.log\n\
\n\
[program:novnc]\n\
command=/usr/bin/websockify --web=/opt/novnc %(ENV_NOVNC_PORT)s localhost:%(ENV_VNC_PORT)s\n\
autorestart=true\n\
priority=20\n\
stdout_logfile=/var/log/supervisor/novnc.log\n\
stderr_logfile=/var/log/supervisor/novnc_err.log\n\
\n\
[program:rosbridge]\n\
command=/bin/bash -c "source /opt/ros/humble/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml"\n\
autorestart=true\n\
priority=30\n\
stdout_logfile=/var/log/supervisor/rosbridge.log\n\
stderr_logfile=/var/log/supervisor/rosbridge_err.log\n\
' > /etc/supervisor/conf.d/supervisord.conf

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Source ROS2\n\
source /opt/ros/humble/setup.bash\n\
\n\
# Source workspace if it exists\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
\n\
# Export display\n\
export DISPLAY=:1\n\
\n\
# Clean up any existing VNC locks\n\
rm -rf /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true\n\
\n\
# Start supervisor\n\
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Create helper script to launch RViz with LEGO config
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
ros2 run rviz2 rviz2 -d /ros2_ws/config/lego_factory.rviz &\n\
' > /usr/local/bin/launch-rviz && chmod +x /usr/local/bin/launch-rviz

# Create helper script to launch Gazebo
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
gz sim -g &\n\
' > /usr/local/bin/launch-gazebo && chmod +x /usr/local/bin/launch-gazebo

# Create helper script to launch rqt
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
rqt &\n\
' > /usr/local/bin/launch-rqt && chmod +x /usr/local/bin/launch-rqt

# Create helper script to launch rqt_graph
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
ros2 run rqt_graph rqt_graph &\n\
' > /usr/local/bin/launch-rqt-graph && chmod +x /usr/local/bin/launch-rqt-graph

# Create helper script to launch rqt_console
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
ros2 run rqt_console rqt_console &\n\
' > /usr/local/bin/launch-rqt-console && chmod +x /usr/local/bin/launch-rqt-console

# Create helper script to launch rqt_topic
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
ros2 run rqt_topic rqt_topic &\n\
' > /usr/local/bin/launch-rqt-topic && chmod +x /usr/local/bin/launch-rqt-topic

# Create helper script to launch rqt_tf_tree
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
ros2 run rqt_tf_tree rqt_tf_tree &\n\
' > /usr/local/bin/launch-rqt-tf-tree && chmod +x /usr/local/bin/launch-rqt-tf-tree

# Create helper script to launch PlotJuggler
RUN echo '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
if [ -f /ros2_ws/install/setup.bash ]; then\n\
    source /ros2_ws/install/setup.bash\n\
fi\n\
export DISPLAY=:1\n\
ros2 run plotjuggler plotjuggler &\n\
' > /usr/local/bin/launch-plotjuggler && chmod +x /usr/local/bin/launch-plotjuggler

# Create RViz config for LEGO Factory
RUN mkdir -p /ros2_ws/config && echo 'Panels:\n\
  - Class: rviz_common/Displays\n\
    Name: Displays\n\
  - Class: rviz_common/Views\n\
    Name: Views\n\
Visualization Manager:\n\
  Class: ""\n\
  Displays:\n\
    - Class: rviz_default_plugins/Grid\n\
      Name: Grid\n\
      Enabled: true\n\
      Line Style:\n\
        Line Width: 0.03\n\
        Value: Lines\n\
      Normal Cell Count: 0\n\
      Plane: XY\n\
      Plane Cell Count: 20\n\
    - Class: rviz_default_plugins/TF\n\
      Name: TF\n\
      Enabled: true\n\
      Frame Timeout: 15\n\
      Frames:\n\
        All Enabled: true\n\
      Marker Scale: 0.5\n\
    - Class: rviz_default_plugins/RobotModel\n\
      Name: RobotModel\n\
      Enabled: true\n\
      Description Source: Topic\n\
      Description Topic:\n\
        Value: /robot_description\n\
    - Class: rviz_default_plugins/MarkerArray\n\
      Name: MarkerArray\n\
      Enabled: true\n\
      Topic:\n\
        Value: /visualization_marker_array\n\
  Global Options:\n\
    Background Color: 48; 48; 48\n\
    Fixed Frame: world\n\
    Frame Rate: 30\n\
  Name: root\n\
  Tools:\n\
    - Class: rviz_default_plugins/Interact\n\
    - Class: rviz_default_plugins/MoveCamera\n\
    - Class: rviz_default_plugins/Select\n\
    - Class: rviz_default_plugins/PublishPoint\n\
  Value: true\n\
  Views:\n\
    Current:\n\
      Class: rviz_default_plugins/Orbit\n\
      Distance: 5\n\
      Name: Current View\n\
      Near Clip Distance: 0.01\n\
      Pitch: 0.5\n\
      Target Frame: <Fixed Frame>\n\
      Yaw: 0.785\n\
Window Geometry:\n\
  Height: 1000\n\
  Width: 1800\n\
' > /ros2_ws/config/lego_factory.rviz

WORKDIR /ros2_ws

EXPOSE 5901 6080 9090

ENTRYPOINT ["/entrypoint.sh"]
