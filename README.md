# BTC 云端价格邮件监控

将本目录的全部内容（包括隐藏目录 `.github`）放在 GitHub 仓库根目录的默认分支。
使用 Python 标准库，无需安装第三方包。电脑关闭后仍由 GitHub Actions 运行。

## 启用

1. 将本目录内容放在 GitHub 仓库根目录。
2. 在 Settings → Secrets and variables → Actions → New repository secret 添加以下三项：

| 名称 | 内容 |
| --- | --- |
| SMTP_USER | 发件 QQ 邮箱完整地址，例如 123456@qq.com |
| SMTP_PASSWORD | QQ 邮箱的 SMTP 授权码，不能使用 QQ 登录密码 |
| MAIL_TO | 收件邮箱完整地址 |

QQ 邮箱需在设置的账号/安全相关选项中启用 SMTP 服务并生成授权码。
默认使用无需 API key 的 CoinGecko 公开接口。若被限流，可选添加 COINGECKO_API_KEY（CoinGecko Demo API key）。
授权码只填 GitHub Secrets，不要写进代码或聊天。

3. 打开 Actions → BTC cloud price monitor → Run workflow，mode 选 `test`。
4. 确认测试邮件到达后，mode 选 `monitor` 执行一次以记录起始价格。
5. 此后每 5 分钟定时检查。可在 Actions 查看执行结果、失败和最近运行时间。

仓库必须允许 Actions 写入内容；此工作流声明 contents: write，若被组织策略或分支保护阻止，需允许状态提交后再启用。避免在运行时编辑 state.json。

## 提醒规则

- 全部使用美元 USD，行情取 CoinGecko 聚合价格。
- BTC 下跌向下触及或跨过 79,000、78,000……70,000 时，每档发一封，包含触发快照的 BTC、ETH、ZAMA 价格和各自报价时间。
- 比如从 79,500 跌到 77,500，会触发 79,000 和 78,000 两封。
- 第一次运行只建立基线，不补发启动前已经跌破的价位。启动价 76,000 时，之后下跌到 75,000 才触发；若以后回到 79,000 以上再跌破，也会触发未发过的档位。
- state.json 随每次任务提交到云端，保存上次价格、待发邮件和已发价位，重启仍保留。
- 发送失败的提醒保留快照，下次重试；任一币种价格缺失、非正数或超过 15 分钟未更新时，不以该样本判断触发。
- 重置全部提醒：先在 Actions 暂停工作流，删除 state.json，再重新启用；下一次建立新基线。

## 运行边界

GitHub 定时任务可能延迟或被跳过；两次采样之间短暂跌破又反弹可能漏报，不是秒级行情服务。
公开仓库长期无活动可能停用定时任务；私有仓库受账号 Actions 配额约束，执行频率对应每月约 8,640 次运行，需留意用量和可能费用。
QQ SMTP 接受邮件不代表一定进入收件箱，请检查垃圾邮件。SMTP 接受后进程中断或状态提交失败时，重试可能重复发信，无法保证分布式严格只发送一次。

行情 API：https://docs.coingecko.com/demo/reference/simple-price
GitHub 定时规则：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

本地逻辑测试：`python -m unittest -v`
只读行情检查：`python monitor.py --check`（无需 API key）。