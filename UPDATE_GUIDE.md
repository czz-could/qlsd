# 📖 自动更新使用说明（方案 A - 配置文件方式）

## 🎯 核心优势

✅ **Token 更换无需重新编译代码** - 只需修改 config.json 并提交到 GitHub  
✅ **动态配置** - 所有旧版本程序下次启动即可使用新配置  
✅ **灵活控制** - 可开关启动检查功能  
✅ **环境切换** - 支持测试/生产环境分离  

---

## 📁 配置文件说明

### `config.json` - 你的 Token 在这里管理

```json
{
  "version_check_url": "https://raw.githubusercontent.com/czz-could/qlsd/refs/heads/main/version_info.json?token=GHSAT0AAAAAAD6FJXGXZ4IYWCFSK6NEMEM62QVK7CQ",
  "check_on_startup": true,
  "current_version": "1.2.0"
}
```

| 字段 | 说明 | 修改后需要做什么 |
|------|------|-----------------|
| `version_check_url` | GitHub Raw 地址（私有仓库必须带 token） | 提交到 GitHub，旧版程序下次启动生效 |
| `check_on_startup` | 是否启动时自动检查更新 | 提交到 GitHub，旧版程序下次启动生效 |
| `current_version` | 当前代码版本号 | 只在编译新版本时使用 |

---

## 🔄 完整工作流程

### 📦 发布新版本（V1.2.0 → V1.3.0）

#### 第 1 步：开发阶段
```python
# gyro_bridge_full.py
CURRENT_VERSION = "1.3.0"  # ← 更新版本号

VERSION_HISTORY = [
    {
        "version": "1.3.0",
        "date": "2026-05-27",
        "title": "新功能发布",
        "changes": [
            "✨ 新增 XX 功能",
            "🐛 修复了 XX 问题"
        ]
    },
    // ... 历史版本
]
```

#### 第 2 步：打包编译
```bash
pyinstaller --onefile --windowed gyro_bridge_full.py
# 输出：dist/桥梁模型箱采集上位机.exe
```

#### 第 3 步：上传到 GitHub Release
1. 访问：`https://github.com/czz-could/qlsd/releases/new`
2. Tag: `v1.3.0`
3. Title: `V1.3.0 - 新功能发布`
4. 上传 `.exe` 文件
5. 点击 **Publish Release**

#### 第 4 步：更新 GitHub 上的 version_info.json
编辑文件：`https://github.com/czz-could/qlsd/edit/main/version_info.json`

```json
{
  "latest_version": "1.3.0",
  "download_url": "https://github.com/czz-could/qlsd/releases/download/v1.3.0/桥梁模型箱采集上位机.exe",
  "update_notes": "✨ 新增功能描述\n🐛 修复的问题"
}
```

#### 第 5 步：验证测试
- 运行 V1.2.0 程序
- 查看日志：`[12:34:56] 🚀 程序启动 - 版本: v1.2.0`
- 应该看到提示：`发现新版本 v1.3.0`
- 点击"去下载"跳转到 Release 页面

---

## 🔧 Token 更换指南

### 何时需要更换？
- Token 过期（程序日志显示检查更新失败）
- 定期安全轮换（建议每 3-6 个月）
- Token 可能被泄露

### 更换步骤

#### 方法 1：在 GitHub 上直接编辑（推荐）

1. **生成新 Token**
   - 访问：`https://github.com/settings/tokens`
   - 点击 **Generate new token (classic)**
   - 勾选权限：`repo`（读取私有仓库内容）
   - 复制生成的 Token

2. **更新 GitHub 上的 config.json**
   - 访问：`https://github.com/czz-could/qlsd/edit/main/config.json`
   - 替换 URL 中的 token：
   ```json
   {
     "version_check_url": "https://raw.githubusercontent.com/czz-could/qlsd/refs/heads/main/version_info.json?token=新的TOKEN",
     ...
   }
   ```
   - Commit changes

3. **验证生效**
   - 重启任何已安装的程序
   - 查看日志：`📡 版本检查: 启用 (✅ 已配置)`
   - 如果能正常检测更新，说明成功 ✅

#### 方法 2：本地修改后推送

```bash
# 1. 编辑本地 config.json
# 2. 提交到 GitHub
git add config.json
git commit -m "更新版本检查 token"
git push origin main
```

---

## 🚀 程序启动时的行为

### 正常情况（V1.2.0 用户）
```
日志显示：
[12:34:56] 🚀 程序启动 - 版本: v1.2.0
[12:34:56] 📡 版本检查: 启用 (✅ 已配置)
[12:34:57] 📥 收到远程版本信息
[12:34:57] ℹ️ 检测到新版本 v1.3.0，弹出提示框
```

### 配置错误（如 Token 失效）
```
日志显示：
[12:34:56] 🚀 程序启动 - 版本: v1.2.0
[12:34:56] 📡 版本检查: 启用 (✅ 已配置)
[12:34:57] ❌ 检查更新失败：HTTP Error 401: Unauthorized
```

### 禁用启动检查
```json
{
  "check_on_startup": false
}
```
```
日志显示：
[12:34:56] 🚀 程序启动 - 版本: v1.2.0
[12:34:56] ℹ️ 启动时自动检查更新已禁用
```

---

## ⚙️ 高级配置

### 多环境支持（可选）

创建两个配置文件：
- `config_test.json` - 测试环境（指向测试仓库）
- `config.json` - 生产环境

通过环境变量切换：
```python
config_path = os.getenv('APP_CONFIG', 'config.json')
```

### 强制更新（可选扩展）

在 `version_info.json` 中添加：
```json
{
  "latest_version": "1.3.0",
  "forced_update": true,
  "deadline": "2026-06-01",
  ...
}
```

然后在代码中检测此标记，如果是强制更新就不允许跳过。

---

## 🐛 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 旧版本不提示更新 | `latest_version` 不大于当前版本 | 确保 [version_info.json](file://e:\CZZ\GD_qlsd\czz\version_info.json) 中的版本号更高 |
| 检查更新失败 | Token 过期 / 网络问题 | 检查日志错误信息，验证 Token 有效性 |
| 下载失败 | `download_url` 不可访问 | 使用 GitHub Release 的资源链接，不是页面链接 |
| 配置文件加载失败 | JSON 格式错误 | 验证 [config.json](file://e:\CZZ\GD_qlsd\czz\config.json) 语法 |

---

## 📋 快速检查清单

发布新版本前：
- [ ] 已更新 `CURRENT_VERSION`
- [ ] 已添加 `VERSION_HISTORY` 记录
- [ ] 编译生成 `.exe`
- [ ] 已上传到 GitHub Release
- [ ] 已更新 GitHub 上的 `version_info.json`
- [ ] 已测试旧版本能检测到更新

---

## 💡 常见问题

**Q: Token 过期会影响哪些版本？**  
A: 所有基于当前代码编译的版本都会受影响，但只需在 GitHub 更新一次 config.json，所有版本下次启动自动使用新 URL。

**Q: 我可以在什么时候更新软件？**  
A: 非强制更新模式下，用户可以随时选择"稍后再说"，在方便的时候再点击"去下载"。

**Q: 如何回滚到旧版本？**  
A: 在 GitHub Releases 中找到旧版本的 Release，下载并覆盖安装即可。旧版本会继续使用最新的 version_info.json。

---

## 📞 技术支持

查看详细文档和示例代码请参考：
- 代码注释
- GitHub Wiki  
- Issues 区