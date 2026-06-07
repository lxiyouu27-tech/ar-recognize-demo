# 拍照识万物 Demo

复刻高德「万花筒识万物」核心体验的最小Demo。手机拍照 + GPS定位 + AI识别周围建筑/店铺/景点。

## 技术栈

- 前端：纯HTML单页，手机浏览器直接打开
- 后端：Python Flask
- 图片识别：通义千问 Qwen-VL（阿里云DashScope）
- 地理信息：百度地图开放平台（周边POI检索）

## 快速开始

### 1. 申请API Key

- **通义千问**：https://dashscope.console.aliyun.com/ → 创建API Key
- **百度地图**：https://lbsyun.baidu.com/ → 创建应用 → 获取AK（需开启「地点检索」权限）

### 2. 安装依赖

```bash
cd ar-recognize-demo
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
export DASHSCOPE_API_KEY=your_dashscope_api_key
export BAIDU_MAP_AK=your_baidu_map_ak
```

### 4. 启动服务

```bash
python server.py
```

### 5. 手机访问

确保手机和电脑在同一WiFi网络下：

```
http://<电脑IP>:5000
```

查看电脑IP：
- macOS: `ifconfig | grep "inet " | grep -v 127.0.0.1`
- Windows: `ipconfig`

> 注意：GPS定位需要HTTPS环境。本地开发时，iOS Safari可能需要在「设置→Safari→高级→实验性功能」中允许非安全来源使用定位。也可以使用 ngrok 等工具暴露HTTPS地址。

## 使用方式

1. 手机浏览器打开页面
2. 允许获取位置权限
3. 点击拍照按钮 → 对准周围建筑/店铺
4. 等待2-5秒 → 查看识别结果

## 工作原理

```
拍照 → 获取GPS坐标
         ↓
百度地图API查询周边200m的POI（建筑名、类型、距离）
         ↓
照片 + POI列表 → 发给通义千问Qwen-VL
         ↓
大模型结合视觉+地理信息，输出识别结果
         ↓
展示为结果卡片
```

## 已知限制

- GPS精度受手机和环境影响，室内可能不准
- 非HTTPS环境下部分浏览器会限制定位和摄像头权限
- 识别速度取决于网络和模型响应时间（通常2-5秒）
- 百度地图POI数据覆盖度因地区而异
