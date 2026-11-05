<!-- SPDX-License-Identifier: MIT -->

# Resume Pro Skill

[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![中文](https://img.shields.io/badge/%F0%9F%87%A8%F0%9F%87%B3_%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-%E5%BD%93%E5%89%8D-blue)](README.md)
[![English](https://img.shields.io/badge/%F0%9F%87%BA%F0%9F%87%B8_English-Available-green)](README.en.md)
[![Docs](https://img.shields.io/badge/%F0%9F%93%96_%E6%96%87%E6%A1%A3-Read-FF7A00)](#文档)

**先问清事实，再写好简历。**

面向中文与国际求职场景的简历 Skill，结合 Agent 的引导与写作能力，以及 Python CLI 的校验与渲染能力，帮助用户从零制作、优化、定向调整和中英文本地化简历。

不编造经历，不一键堆砌套话，也不把中英文简历当作简单的逐句翻译。简历交付格式仅为 **HTML**，使用 **A4** 打印布局。

## 能做什么

| 你的需求 | 工作方式 |
|---|---|
| 从零制作简历 | 分步收集信息，检查是否足够，再追问缺失内容 |
| 优化已有简历 | 提取事实，请用户确认，评估并选择保留或更换模板 |
| 只想知道问题 | 提供诊断，不擅自改写 |
| 针对岗位调整 | 对照职位描述（JD）选择经历，分析匹配点、缺口与风险 |
| 不确定适合什么岗位 | 根据已有经历推荐岗位方向，指出需要补充的证据 |
| 中英文简历转换 | 基于同一份事实，按目标市场重新组织内容与表达 |
| 更换模板或添加照片 | 保留事实；照片可选，不设置时不留下占位框 |

面向学生、实习生、应届生、转行者、有经验的求职者等不同人群。主要市场配置包括 `cn_internet` 与 `intl_en`；其他市场配置的适用范围见[市场矩阵](docs/market-matrix.md)。

不包含求职信、面试辅导、薪资谈判、职位抓取或自动投递。

## 核心原则

- **事实与证据优先。** 简历要点关联来源，区分已核实、用户自述、估计和未知信息。只有估计或未知来源支撑的数字会被检查拦截；用户自述不等于外部核实。
- **先引导，再生成。** 信息不足时提出针对性问题，不用虚构内容补齐；先询问海投还是定向投递，再决定如何选择经历。
- **写作框架由用户选择。** 使用 STAR、XYZ、FAB、CAR、结果优先或保留个人语气前，先获得同意。
- **不同市场，不同重点。** 按市场与求职阶段调整栏目、顺序、页数和照片策略；中文校园场景强调教育、基础技能、真实实习与项目贡献。
- **不添加“求职意向”栏目。** 目标岗位用于内容选择和文件命名，不作为简历中的额外一栏。
- **HTML-only，A4。** 输出自包含 HTML；需要 PDF 时由用户在浏览器中选择 A4 打印。没有 DOCX、LaTeX 或图片简历导出。
- **规则校验与人工判断分工。** CLI 负责结构、证据规则、模板和输出检查；Agent 与用户负责表达质量、事实确认和最终审阅。

## 快速开始

### 1. 准备运行环境

需要 **Python 3.10+**。在本项目根目录执行：

```bash
python -m pip install -e .
resume --version
resume --help
```

这里使用可编辑安装，让 CLI 直接读取源码目录中的模板、规则和 Schema。安装后请保留该目录；首次安装依赖可能需要联网。

- 安装 Edge、Chrome 或 Chromium，可启用浏览器辅助的排版 QA；不可用时部分检查退回估算并给出警告。
- 导入旧版 DOC / RTF 文件需要 LibreOffice。
- 使用 Agent 时，将本项目作为 Skill 加载，入口为 [SKILL.md](SKILL.md)。Agent 需要能够运行本地命令；导入 Skill 不代表 Python 依赖已经就绪。具体配置见[安装说明](docs/install.md)。

### 2. 从零建立简历资料

以下以中文互联网校招 / 实习场景为例。在独立的求职工作目录执行：

```bash
resume init --market cn_internet --persona student_with_internship
resume intake
resume check
resume profile
```

按引导回答问题。检查发现缺项时，先补充信息，不要跳过阻断直接生成。资料保存在当前工作目录的 `.resume/` 中。

### 3. 选择写作方式并生成

仅在用户同意结果优先框架后使用下面的 `--framework result_first`；也可以换成用户选择的其他框架。

```bash
resume new --role "Backend Engineer" --market cn_internet --persona student_with_internship --framework result_first
```

将下面的 `<slug>` 替换为上一条命令返回的申请标识。确认内容后检查并构建：

```bash
resume lint --app <slug>
resume build <slug> --yes
resume audit <slug>
```

`--yes` 用于确认仅达到最低充分度的资料，不能绕过信息不足或其他硬性失败。打开生成的 HTML 检查内容与布局；需要 PDF 时使用浏览器的 A4 打印功能。

### 4. 已有简历或目标岗位

下面是独立的使用示例，文件路径和 `<slug>` 需替换为自己的输入：

```bash
# 诊断已有简历
resume review resume.pdf --market cn_internet --persona experienced

# 提取资料并评估原模板；仍需用户确认提取结果
resume optimize resume.docx --market cn_internet --persona experienced

# 对照 JD 分析匹配情况，并推荐岗位方向
resume match --app <slug> --jd jd.md
resume recommend --app <slug>

# 查看模板，或为申请添加可选照片
resume templates
resume photo portrait.jpg --app <slug>

# 基于事实创建英文版本
resume localize <slug> --to en --role "Backend Engineer" --yes
```

本地化需要 Agent 与用户补齐目标语言的表达。缺少目标语言内容时，CLI 会报告缺口，而不是自行翻译或编造；事实一致性检查失败时会阻止正式交付。

更完整的操作见[使用演练](docs/walkthrough.md)和 [CLI 契约](docs/cli-contract.md)。

## 输入、模板与输出

**输入：** DOCX、文本型 PDF、HTML、Markdown、TXT；DOC / RTF 需要 LibreOffice。当前不支持扫描型 PDF 的 OCR。

**模板：** 中文与英文分开组织，不在正式简历中显示 CN / EN 标签。中文简历使用中文模板，英文简历使用英文模板，跨语言混用会被拒绝。

| 语言 | 目录 | 随源码提供的模板 |
|---|---|---|
| 中文 | [`templates/cn/`](templates/cn/) | `campus`、`zh-professional` |
| English | [`templates/en/`](templates/en/) | `ats-classic`、`modern-sidebar`、`editorial`、`executive` |

照片插槽在未设置照片时完全收起；`intl_en` 按市场策略不显示照片。模板效果需要结合实际内容人工审阅，自动检查不代表设计审核或所有 ATS 的兼容性保证。

**输出：** 正式 HTML、非权威的可编辑 HTML 副本，以及检查报告。定向申请通常在文件名中包含岗位。浏览器中对可编辑副本的修改不会自动写回事实库。

## 工作原理

```text
引导收集 → 充分度检查 → 市场与人群配置 → 事实选择
        → 申请模型 → 写作与检查 → 可选本地化 → HTML 渲染 → QA
```

- **事实库（vault）**：保存长期经历、证据记录和不同语言的措辞。
- **申请模型（application）**：保存某次申请的事实选择、目标市场、写作设置和模板。
- **模板契约**：通过 `data-slot` 声明插槽和内容要求，由确定性渲染器填充。

CLI 在本地处理资料，不提供遥测或自动上传功能。Agent 所使用的模型服务是否接收对话或文件内容，取决于你的客户端与模型配置，不能据此视为整个工作流完全离线。

## 文档

详细技术文档目前主要使用英文；此处的语言切换仅切换项目 README。

| 文档 | 内容 |
|---|---|
| [安装说明](docs/install.md) | 环境要求与 Skill / CLI 配置 |
| [快速开始](docs/quickstart.md) | 引导收集、检查与常用命令 |
| [使用演练](docs/walkthrough.md) | 按场景完成一次申请 |
| [Agent 入口](SKILL.md) | 触发条件、工作流程与不可违反的规则 |
| [市场矩阵](docs/market-matrix.md) | 市场与人群配置的适用范围 |
| [中文简历规则](docs/cn-resume-rules.md) | 中文场景的内容与结构要求 |
| [信息收集与充分度](docs/intake-and-sufficiency.md) | 追问逻辑与生成门槛 |
| [写作引擎](references/writing-engine.md) | 框架、措辞与证据约束 |
| [触发与路由](docs/triggers-and-routes.md) | 不同用户意图的处理方式 |
| [CLI 契约](docs/cli-contract.md) | 命令、输入输出与退出码 |
| [模板契约](docs/template-contracts.md) | 插槽、预算与模板规则 |
| [评估与限制](docs/evaluation.md) | 测试、QA 与 ATS 检查边界 |
| [开源政策](docs/open-source-policy.md) | 代码、模板与素材的使用原则 |

## 开发与验证

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

公开测试覆盖事实库、证据规则、信息收集、导入、选择、模板、渲染、本地化与 QA 等模块。测试通过不等于真实招聘效果、所有 ATS 兼容性或上游代码来源已经得到认证。

贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

本项目采用 [MIT License](LICENSE)。参考项目与相关许可说明见 [ATTRIBUTIONS.md](ATTRIBUTIONS.md)；第三方内容仍受其各自许可约束。
