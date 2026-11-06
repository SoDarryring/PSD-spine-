# 第三方组件

根目录 MIT 许可证适用于本项目自有代码。第三方代码和发行包中的依赖保留各自的许可证；本文件不替代其原文。

| 组件 | 用途与来源 | 许可证位置 |
| --- | --- | --- |
| PhotoshopToSpine v7.42 | [Esoteric Software 官方脚本](https://github.com/EsotericSoftware/spine-scripts/tree/master/photoshop)，修订 `69c429295b5b19f66f959ad2ac644d40a14121e5` | [上游 LICENSE](vendor/photoshop-to-spine/LICENSE) 及 JSX 文件头的声明 |
| CustomTkinter | [界面控件与缩放](https://github.com/TomSchimansky/CustomTkinter) | 发行包 `licenses/` 及依赖包元数据 |
| tkinterdnd2 / TkDnD | [原生拖放](https://github.com/Eliav2/tkinterdnd2) | 发行包 `licenses/`、[TkDnD 原始声明](vendor/licenses/TkDnD-license.terms) 及依赖元数据 |
| Pillow | [图像支持](https://github.com/python-pillow/Pillow) | 发行包 `licenses/` |
| darkdetect / packaging | 界面和依赖运行支持 | 发行包 `licenses/` |
| CPython / Tcl / Tk | 便携版解释器与桌面运行库 | 发行包 `licenses/`，另保留 [Tcl 原始声明](vendor/licenses/Tcl-license.terms) |
| PyInstaller | [便携包构建与引导程序](https://github.com/pyinstaller/pyinstaller) | 发行包 `licenses/`；沿用上游的引导程序许可例外 |

官方 JSX 以原始字节保存，在运行时临时替换入口、提供参数、处理错误、恢复文档状态。上游图层导出实现仍由其作者持有版权。自定义原点、输出管理与界面属于本项目的集成逻辑。

构建脚本会把实际构建环境中可获得的依赖许可证复制到发行包的 `licenses/`，并记录构建版本。修改依赖或分发方式时，请同时检查其许可证。

Photoshop 和 Spine 需要用户自行合法安装并授权，不属于本项目的开源授权范围，也不随发行包提供。本项目不代表 Adobe 或 Esoteric Software。
