# PSD 一键转 Spine

把分层 PSD / PSB 转为 **Spine 3.8.99 可编辑工程**的 Windows 桌面工具。通过 Photoshop 调用官方 PhotoshopToSpine 脚本导出图层，再调用 Spine 命令行生成 `.spine`。

[下载 Windows 便携版](https://github.com/SoDarryring/PSD-spine-/releases) · [详细使用说明](docs/usage.md) · [参与开发](CONTRIBUTING.md)

**使用条件：已安装且可正常运行的 Photoshop；生成 `.spine` 还需要已激活、能运行 3.8.99 的 Spine。** 只导出 JSON 和图片时不需要 Spine。便携版不需要安装 Python，也不需要手动安装 PS 插件。

本工具是独立开源项目，与 Adobe、Esoteric Software 无隶属或背书关系。仓库及发行包不包含 Photoshop、Spine、激活信息或游戏素材。

## 能做什么

| 功能 | 说明 |
| --- | --- |
| 批量转换 | 多选文件，或将 PSD、PSB、文件夹拖入窗口 |
| 保留摆放 | 使用官方插件保留图层位置、绘制顺序及其支持的标签 |
| 精简输出 | 默认只输出 `.spine` 和 `images/` |
| 就近保存 | 默认在每个 PSD 旁创建同名工程文件夹，重名自动编号 |
| 原点定位 | 可选最底层图层的内容中心作为 Spine 原点，包含嵌套分组 |
| 图片选项 | 缩放、留边、透明边裁剪、隐藏层和背景层过滤 |
| 桌面界面 | 圆角卡片布局，窗口和控件随系统 DPI 缩放 |

生成的是图层初始摆放工程。普通 PSD 没有骨骼标签时，附件默认挂在 root 下；骨骼绑定、权重和动画需要继续在 Spine 中制作。

## 使用便携版

1. 从 [Releases](https://github.com/SoDarryring/PSD-spine-/releases) 下载 Windows x64 **EXE 单文件版**。
2. 双击下载的 EXE。使用、复制或分发这个 EXE 即可，无需附带 `licenses` 文件夹或使用说明文件。
3. 拖入源文件，确认设置；通常保持默认值即可。
4. 点击“生成 Spine 工程”，完成后点击“打开输出”。
5. 使用 Spine **3.8.99** 打开生成的工程。

从 v1.1.1 开始，分发文件只有 EXE。必要的项目许可证和第三方许可原文内置，在右上角“关于”中查看；使用说明保留在本仓库，不另附文件。

例如，转换 `角色.psd` 后会在它旁边得到：

```text
角色/
├── 角色.spine
└── images/
    ├── 身体.png
    └── 头部.png
```

不会保存原 PSD。软件先处理临时副本，完成后关闭本次创建的 Photoshop 文档。转换期间请让 Photoshop 空闲，避免打开或修改其他文档干扰脚本。

## 从源码运行

需要 Windows、Python 3.11 或更新版本，及前述 Photoshop / Spine 环境。在项目根目录运行：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python src/psd_to_spine_gui.py
```

命令行也可以转换；默认输出到输入文件旁边：

```powershell
python src/psd_to_spine.py "input/角色.psd"
python src/psd_to_spine.py "input/角色.psd" --bottom-layer-origin --scale 50
python src/psd_to_spine.py "input/角色.psd" --json-only
```

支持通过 `--spine` 或 `SPINE_EXE` 指定本机 Spine 程序。更多参数见 `python src/psd_to_spine.py --help`。

## 测试与打包

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -t . -v
pwsh -File scripts/build.ps1
```

如果依赖安装在前述虚拟环境中，打包时使用 `pwsh -File scripts/build.ps1 -PythonExecutable .venv/Scripts/python.exe`。

打包产物位于 `dist/`，发行附件只提供可直接运行的 EXE。构建时先收集必要许可原文，再嵌入 EXE；会把 EXE 单独复制到空目录、从该目录启动，验证内置许可查看器及运行资源。GitHub Actions 在 Windows 上执行相同流程。常规测试不启动 Photoshop 或 Spine。

真实 Photoshop / Spine 集成测试是显式启用的本地检查，使用代码生成的色块样例，不需要提供或上传美术资源：

```powershell
$env:PSD_SPINE_INTEGRATION = "1"
python -m unittest tests.test_integration_photoshop -v
```

已验证的范围及尚未覆盖的项目见 [验证记录](docs/validation.md)。

## 许可证与上游

自有代码使用 [MIT License](LICENSE)。内置官方 PhotoshopToSpine v7.42 原件及其许可证保存在 [vendor/photoshop-to-spine](vendor/photoshop-to-spine)，固定上游修订并在运行时校验文件指纹；第三方组件保留各自许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

参考：[官方 Photoshop 插件](https://github.com/EsotericSoftware/spine-scripts/tree/master/photoshop)、[Spine 命令行文档](https://esotericsoftware.com/spine-command-line-interface)。
