# 知岸小程序部署与上传流程

这份文档按知岸 v0.3 的现有目录编写。先部署后端和 HTTPS，再配置小程序，最后在微信开发者工具上传审核。

## 一、先准备这些东西

### 服务器和域名

- 一台可运行 Docker Engine / Docker Compose 的 Linux 服务器。
- 一个域名，DNS 的 A 记录指向服务器。
- 服务器放行 80、443 端口。
- 如果服务器在中国大陆，域名需要完成 ICP 备案。

### 微信小程序账号

- 在 [微信公众平台](https://mp.weixin.qq.com/)注册小程序。
- 取得正式 AppID。
- 在后台“开发设置”生成 AppSecret。
- 完成小程序备案，按后台要求完成主体核验。

### 本地开发机

- Node.js 22.12+ 或 24+
- 微信开发者工具
- Git 或能够把项目代码复制到服务器的方式

## 二、部署后端和网页

### 1. 上传项目

把 `E:\ztest\zhian-study` 项目完整放到服务器，例如 `/opt/zhian-study`。

不要只上传 `dist/`，因为 Dockerfile 需要一个完整的项目上下文来构建前端和启动 FastAPI。

### 2. 创建部署配置

```sh
cd /opt/zhian-study
cp deploy/.env.example deploy/.env
```

编辑 `deploy/.env`，至少填写：

```text
ZHIAN_DOMAIN=study.example.com
ZHIAN_BOOTSTRAP_TOKEN=替换成随机长口令
ZHIAN_WECHAT_APPID=你的微信小程序AppID
ZHIAN_WECHAT_SECRET=你的微信小程序AppSecret
ZHIAN_ALLOW_REGISTRATION=false
ZHIAN_TIMEZONE=Asia/Shanghai
```

`ZHIAN_BOOTSTRAP_TOKEN` 可以用 Python 生成：

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

不要把 `deploy/.env` 提交到代码仓库，也不要发到聊天里。

### 3. 启动服务

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
```

检查容器：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
curl https://study.example.com/api/health
```

健康接口应返回类似：

```json
{"status":"ok","version":"0.3.0","mode":"account-ready"}
```

首次打开 `https://study.example.com`，创建你的知岸账号。旧版本数据通过“导出完整数据 → 新服务导入与恢复”迁移。

## 三、配置微信后台

### 1. 填写 AppID 和 AppSecret

在微信公众平台确认：

- 小程序 AppID 与 `miniapp/src/manifest.json` 中的 `mp-weixin.appid` 一致。
- `ZHIAN_WECHAT_APPID` 与同一个 AppID 一致。
- `ZHIAN_WECHAT_SECRET` 只放在服务器环境变量中。

### 2. 配置合法域名

在“开发管理 → 开发设置 → 服务器域名”中，把 HTTPS 地址加入 request 合法域名：

```text
https://study.example.com
```

不要填写 `/api`、端口号或 `127.0.0.1`。域名必须使用 HTTPS，并在微信后台完成配置。

### 3. 配置隐私和类目

- 在后台填写用户隐私保护指引。
- 隐私政策可使用 `publish/wechat/privacy-policy.html`，部署到你的正式域名。
- 服务类目按学习记录工具申报，具体以后台当前类目和审核结果为准。
- 补齐账号注销或数据删除入口，或提供清晰的数据删除申请方式。

## 四、配置小程序前端

在项目目录执行：

```powershell
cd E:\ztest\zhian-study\miniapp
npm ci
Copy-Item .env.example .env.production.local
```

编辑 `miniapp/.env.production.local`：

```text
VITE_API_BASE_URL=https://study.example.com
```

这个值只填写服务原点，不要在后面添加 `/api` 或斜杠。不要把 AppSecret、初始化口令、登录令牌写进任何 `VITE_*` 变量。

编辑 `miniapp/src/manifest.json`，填写正式 AppID：

```json
{
  "mp-weixin": {
    "appid": "wx你的正式AppID"
  }
}
```

运行发布前检查和构建：

```powershell
npm run check:release
npm run build:mp-weixin
```

构建成功后，产物目录是：

```text
E:\ztest\zhian-study\miniapp\dist\build\mp-weixin
```

## 五、在微信开发者工具中预览和上传

### 1. 导入项目

打开微信开发者工具，选择“导入项目”：

- 项目目录：`E:\ztest\zhian-study\miniapp\dist\build\mp-weixin`
- AppID：填写正式 AppID

不要导入项目根目录、`miniapp` 源码目录或 `dist/dev` 目录。

### 2. 本地编译和真机预览

1. 点击“编译”。
2. 确认首页不是空白页，登录页可以显示。
3. 使用开发者工具的“预览”生成二维码。
4. 用 Android 和 iPhone 各扫一次，测试登录、记录、专注、复习和统计。

真机测试要求手机能访问 `https://study.example.com`，不能使用 `127.0.0.1`。

### 3. 上传体验版

在微信开发者工具右上角点击“上传”：

- 版本号：例如 `0.3.0`
- 项目备注：例如“知岸学习记录工具 v0.3.0，完整主流程”

上传完成后，回到微信公众平台：

1. 进入“版本管理”。
2. 在“开发版本”中找到刚上传的版本。
3. 提交审核。
4. 填写功能页面、服务类目、测试账号和审核说明。
5. 审核通过后点击“发布”，用户才能正式使用。

## 六、提交审核时填什么

审核功能页建议选择：

- 今日概览
- 学习计划
- 复习卡片
- 统计复盘
- 登录与账号

审核账号使用合成账号，只填在微信后台，不写入代码仓库。审核说明可以使用：

> 本小程序为个人学习记录工具。用户创建账号后可记录学习计划、学习时长、复习卡片和个人统计。数据默认仅用户本人可见，不公开、不分享，不提供课程、直播、题库售卖或培训报名。微信登录仅用于绑定已有账号。

## 七、常见问题

### 1. 为什么开发者工具能上传，但真机请求失败？

通常是以下原因：

- 服务器使用 HTTP，真机需要 HTTPS。
- 域名没有加入微信后台的 request 合法域名。
- `VITE_API_BASE_URL` 写错，或误加了 `/api`。
- AppID 和 AppSecret 不是同一个小程序。

### 2. 为什么 `npm run check:release` 失败？

它会检查：

- `manifest.json` 是否填写了真实 `wx` 开头的 AppID。
- `VITE_API_BASE_URL` 是否是正式 HTTPS 域名。
- `VITE_*` 变量中是否疑似写入了密码、令牌或 Secret。

按命令输出的错误逐项修复。

### 3. 为什么不能把 AppSecret 写进小程序？

小程序包会被下载到用户设备，任何写进前端包的密钥都不再是秘密。AppSecret 只能配置在服务器环境变量里，由后端调用微信接口。

### 4. 备案没完成可以先上传吗？

可以先把开发版上传到后台做体验测试，但正式发布和备案要求以后台当期规则为准。准备上线前先完成小程序备案、主体核验、隐私声明和合法域名配置。

## 八、最短执行顺序

```text
服务器 + 域名 + HTTPS
        ↓
Docker 启动知岸后端
        ↓
微信后台填写 AppID、AppSecret、合法域名
        ↓
miniapp 填写正式 AppID 和 HTTPS 地址
        ↓
build:mp-weixin
        ↓
微信开发者工具导入 dist/build/mp-weixin
        ↓
真机预览 → 上传体验版
        ↓
公众平台提交审核 → 审核通过 → 发布
```
