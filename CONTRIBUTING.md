# 参与开发

请先阅读 [README](README.md) 配置源码环境。提交前运行：

```powershell
python -m unittest discover -s tests -t . -v
```

GUI 与原生拖放测试需要 Windows 桌面会话。真实 Photoshop / Spine 集成测试只在显式设置 `PSD_SPINE_INTEGRATION=1` 后运行；CI 不安装或激活这些商业软件。

| 目录 | 作用 |
| --- | --- |
| `src/psd_to_spine.py` | 官方导出脚本适配、参数验证、工程导入和输出管理 |
| `src/psd_to_spine_gui.py` | 界面、DPI 适配、原生拖放和任务队列 |
| `tests/` | 常规检查及显式启用的集成测试 |
| `scripts/` | 构建和依赖许可证收集 |
| `vendor/` | 固定版本的上游脚本与原始许可证 |
| `docs/` | 使用方法与验证范围 |

修改官方插件集成时，请保留上游原件，在适配器内进行必要处理。更新原件时须同时更新上游修订号、SHA256、集成测试和第三方说明。

请只提交源码、测试、配置和文档。不要提交 PSD、美术资源、生成的工程、缓存、商业软件、激活数据或包含个人信息的日志。需要分享重现材料时，优先使用合成样例。

Issue 请说明软件版本、Windows / Photoshop / Spine 版本、选项和可复现步骤。提交截图或日志前，请移除个人路径、账号和激活信息。
