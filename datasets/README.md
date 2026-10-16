# 采集数据归档

原始采集数据保存在本仓库的 [data-2026-10-16 Release](https://github.com/xfang8343/A2/releases/tag/data-2026-10-16) 中。`data/` 不直接纳入 Git 历史。

- `data-inventory.json`：完整文件路径、文件大小、文件数量及总大小。
- `data-files.sha256`：每个原始文件的 SHA-256 校验值。
- `archive-parts.sha256`：Release 中各压缩分卷的 SHA-256 校验值，按拼接顺序排列。
- `sdk-archive.sha256`：原始 SDK ZIP 的 SHA-256 校验值。

## 下载并恢复

需要 Bash、GitHub CLI (`gh`)、`sha256sum` 和 GNU tar。克隆仓库后运行：

```bash
bash scripts/download_data.sh
```

脚本会下载全部分卷、校验分卷、拼接并解压到项目根目录，然后校验全部原始文件。现有 `data/` 不会被覆盖。下载目录 `.download-assets/` 保留以便重试，成功后可自行删除。

请预留约 26 GiB 用于原始数据，以及压缩分卷所需的额外空间。Git 克隆本身不下载这些数据。

仅校验已有数据：

```bash
bash scripts/download_data.sh --verify
```

原始 SDK ZIP 也保存在同一 Release 中；已解压的 SDK 文件保留在 Git 仓库中：

```bash
gh release download data-2026-10-16 --repo xfang8343/A2 \
  --pattern 'AimDK-A2-Ultra-V1.3-0130.zip'
sha256sum -c datasets/sdk-archive.sha256
```

该归档保留原始 `data/` 目录结构及文件内容。分卷必须全部下载并按顺序拼接；单个分卷不能独立解压。标注和 `processed/` 处理结果随代码直接纳入 Git。
