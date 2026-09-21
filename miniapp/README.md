# 知岸 · 微信小程序

uni-app（Vue 3 + TypeScript）小程序端，与现有 FastAPI 后端共用学习数据。前端业务类型引用 `../src/types.ts`，不复制后端统计、复习排期或账号隔离规则。

## 当前功能

- 今日：真实学习时长、自动打卡、每日目标、连续学习、正确率、今日计划、最近记录。
- 计划：按周 / 日期、所有待办、已完成筛选；新增、编辑、删除；从计划计时或填写实际学习记录。
- 复习：到期 / 全部 / 归档；先回忆再揭示答案；按反馈安排下次复习并记录实际用时；编辑、归档、恢复。
- 统计：7 / 30 天时长与正确率、科目分配、打卡日历、逐日记录、未来一周复习数量。
- 我的：考试与每日目标、自定义科目、记录筛选与编辑、账号密码登录、注册、改密、退出、微信绑定与解绑。
- 专注：开始、暂停、继续、结束并保存；重启后恢复、切后台后按时间戳计算、按服务和账号分别保存。

微信登录接口已实现；真实微信登录与发布需配置自己的 AppID、AppSecret 和 HTTPS 服务。当前构建使用游客 AppID，未连接真实微信账号，也未发布到微信。

图标、名称、简介、服务类目、备案清单、隐私政策和审核截图见 [微信发布资料包](../publish/wechat/README.md)。

## 本地启动

项目后端需要 v0.3。首次在项目根目录运行 `start.cmd` 或 `start.ps1`，后端地址默认为 `http://127.0.0.1:8765`。若旧服务仍在运行，应先停止再启动新版。

在 `miniapp` 目录执行（Node.js 22.12+ 或 24+）：

```powershell
npm ci
# 仅首次配置；已有 .env.local 时保留自己的配置。
Copy-Item .env.example .env.local
npm run dev:mp-weixin
```

在微信开发者工具中导入 `miniapp/dist/dev/mp-weixin`。将真实微信 AppID 填入 `src/manifest.json` 的 `mp-weixin.appid` 后重新编译。不要把项目根目录或 Vue 源码目录当作微信项目导入。

本机接口由 `.env.local` 中的 `VITE_API_BASE_URL` 指定，填写服务原点，例如 `http://127.0.0.1:8765`，不要附加 `/api`。开发者工具访问本机 HTTP 接口需要使用其本地开发调试设置；真机和正式版应使用已配置为合法请求域名的 HTTPS 服务。

还可以先在浏览器验证界面和账号流程：

```powershell
npm run dev:h5
```

打开 `http://127.0.0.1:5174`。H5 开发请求通过代理进入 `ZHIAN_DEV_API_TARGET` 指定的后端，默认仍是 8765。微信快捷登录按钮只在微信小程序中显示。

构建 H5 后，重新启动根项目后端，即可在 `http://127.0.0.1:8765/mini/` 查看同一套手机界面。这是本地预览入口，使用根项目同一数据库；不是独立的示例数据站点。

```powershell
npm run build:h5
```

## 账号与微信登录

已有网页版账号可以直接登录，记录、目标、计划和复习进度都会沿用。首个账号会接管此服务原有本地数据；本机可初始化，远程初始化必须输入后端配置的口令。是否允许其他账号注册仍由 `ZHIAN_ALLOW_REGISTRATION` 决定。

在后端启动环境配置：

```text
ZHIAN_WECHAT_APPID=你的微信小程序AppID
ZHIAN_WECHAT_SECRET=对应的AppSecret
```

后端不会自动读取项目根目录 `.env` 文件；本地请通过启动环境设置，Docker Compose 则使用 `deploy/.env`。AppSecret 不应写进小程序源码、`manifest.json`、`VITE_*` 变量或聊天消息。

微信登录流程：

1. 小程序 `uni.login` 获取临时 code，由后端请求微信 `jscode2session`。
2. 后端按 `AppID + openid` 查找绑定；已绑定则签发知岸登录令牌。
3. 未绑定则返回有效期 5 分钟、只能使用一次的绑定凭证。用户必须验证已有知岸账号密码后才能绑定；新用户可先注册知岸账号。
4. 在“我的 → 绑定微信”中也可以验证密码后绑定。已绑定其他账号的微信、已有其他微信的账号均不会被自动覆盖。
5. 解绑需要当前密码，并撤销此账号全部小程序登录令牌；改密会同时撤销网页和小程序会话，再为当前客户端签发新会话。

小程序采用独立的随机 Bearer 令牌，默认有效期 7 天；数据库只保存令牌散列。每次业务请求携带 `X-Workspace-ID`，账号切换后丢弃旧请求结果、清空已显示的数据。网页继续使用 HttpOnly Cookie 与 CSRF 防护，两个令牌空间不可互换。后端不保存或返回微信 `session_key`。

主要接口：

| 接口                                        | 用途                                          |
| ------------------------------------------- | --------------------------------------------- |
| `GET /api/mini/auth/config`                 | 注册和微信登录是否可用                        |
| `POST /api/mini/auth/register`、`login`     | 账号注册 / 登录                               |
| `GET /api/mini/auth/session`                | 当前账号与绑定状态                            |
| `POST /api/mini/auth/wechat`                | code 换登录令牌或绑定凭证                     |
| `POST /api/mini/auth/wechat/bind`、`unbind` | 验证密码后绑定 / 解绑                         |
| `POST /api/mini/auth/password`、`logout`    | 改密 / 撤销当前小程序令牌                     |
| `GET /api/workspace`                        | 一次读取当前账号完整工作区                    |
| `POST /api/reviews/{id}/archive`            | 微信请求兼容的归档接口，网页原 PATCH 入口保留 |

## 同步与计时边界

前台每 30 秒同步，回到小程序、进入主要页面和下拉刷新时也会读取最新数据。确认保存的学习记录进入共用后端；离线不会虚报保存成功，本版没有离线提交队列。

未保存的专注只保存在当前手机，不能在另一台设备接续。账号切换或退出时暂停并保留原账号的计时；切后台继续按真实时间计算，24 小时封顶。结束时按分钟向上取整，可手动核对；跨午夜默认归入开始日期。

学习记录与复习提交使用稳定的请求编号，重试不会重复累计学习时长。复习还校验卡片版本；另一设备已更新时需要重新读取。普通计划、目标与记录编辑沿用后端“最后保存生效”的规则。

JSON/CSV 备份恢复仍使用网页版。当前未实现订阅消息、微信支付、题库接入或云函数。

## 构建与发布准备

```powershell
npm test
npm run build:mp-weixin
npm run build:h5
```

微信构建输出为 `dist/build/mp-weixin`，包含 `app.json`、页面 WXML / WXSS / JS、组件、图标与 `project.config.json`，可直接导入微信开发者工具。源码不会包含服务器密码或 AppSecret。

准备正式发布时，在 `.env.production.local` 配置 HTTPS 原点，在 `src/manifest.json` 填入 AppID，再运行：

```powershell
npm run build:release
```

该命令先检查真实 AppID、HTTPS 域名以及前端变量中的误放凭据，再构建小程序。检查通过不代表微信审核或真机验证已完成。仍需在微信后台配置合法请求域名，并按账号主体和服务类目完成相应备案、隐私声明、体验与审核步骤。

服务端部署沿用 `../deploy/`。Compose 为应用增加了只用于出站请求的网络，以访问微信 HTTPS 接口；应用端口仍不映射到宿主机。现有 Docker 镜像提供网页和 API，小程序包在微信开发者工具上传；本地 `/mini/` 预览只在存在 H5 构建目录时启用。

## 工程说明

```text
src/pages/         五个主页面，以及登录、记录、编辑、专注与账号页面
src/api.ts         uni.request、令牌与账号保护、错误处理
src/session.ts     登录持久化与切换通知
src/workspace.ts   工作区刷新与旧响应隔离
src/focus.ts       时间戳计时与分账号恢复
src/types.ts       复用网页业务类型，补充小程序登录类型
src/style.css      浅绿与米白的移动界面
src/static/tabs/   原生 tabBar PNG 图标
scripts/           图标生成、发布配置检查
```

uni-app 编译器固定在已验证的 Vue 3 版本。构建依赖的兼容补丁统一写在 `package.json` 的 `overrides`，应与锁文件一同提交；不要直接运行会跨版本替换 uni-app 的 `npm audit fix --force`。修改这些覆盖版本后，需要重新构建微信包、H5，并运行接口和前端测试。
