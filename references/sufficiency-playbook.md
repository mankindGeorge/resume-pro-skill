# Sufficiency playbook

The complete content-sufficiency rules behind the one-line checklist in `SKILL.md` § Content sufficiency. Nothing here is optional: the checklist is the index, this playbook is the working method. The mechanically checkable parts are hard lint checks (framework labels and order, per-locale bullet length, result points with data — see [Writing engine](writing-engine.md) §4); the agent owns the conversation that gets real content before any of those checks can pass.

## 1. Packaging is the core work

- 项目包装是核心工作。HR 要看到实打实的内容：每个保留条目都要有背景、你的角色、动作和结果。把原始事实重写成「问题—决策—影响」，不要只复述用户原话。
- Every kept role or project must answer four things: background or problem, the user's role, the user's action, and the result. Technical stack alone is not a result.
- 合格项目的充分性标准：一个像样的项目展示要覆盖这些维度——背景/问题、角色分工、方案与取舍、难点与解决、评估/验证、部署/交付、成果与数据、使用与反馈。只写技术栈和功能清单不算合格。对照这个清单看已给内容覆盖了哪些维度。
- When the user's first description is too thin to present a project well, do not wait for them to volunteer more: walk the uncovered dimensions and ask, one question at a time, for what they may not have thought to mention — what was hard and why, what was decided or traded off, how it was tested or evaluated, how it was deployed or delivered, what data or user feedback followed, what was reused or open-sourced. A real project can carry much more than a first summary.
- When a bullet only names tools or duties, ask for the outcome behind them: a number, scope, artifact, or user-visible change.
- If the user gives technology without background or results, ask one question: can you supply it, or should I rephrase only what you already gave? Add nothing on my own.

## 2. Write to the chosen framework

- 框架和内容包装写在同一个文档：[Writing engine](writing-engine.md)。六个框架（STAR/XYZ/FAB/CAR/结果优先/个人语气）各有自己的包装配方、标签分点和示例，按所选框架的配方写，不要都按一种框架写。
- Follow the selected framework's packaging recipe while collecting; it lists exactly which slots to ask for. Ask only for the slots that are missing.
- Render each kept project as 3–4 labeled points using the chosen framework's recipe and label set. Each point is a complete, substantial sentence with real detail; never a one-line fragment.
- 项目/实习介绍每行文字至少占可打印宽度的 2/5。换行后一行只剩几个字时，优先扩句（只展开已有事实），其次精简句子重新排布，不要留孤字行。
- A `核心成果：` point must say what problem was solved and what changed, not just list an award or repeat the technology. A `解决方案：` point must explain the pain point and why the approach fits it. Remove filler such as launch dates unless they prove impact.
- All points render as labeled paragraphs or plain lines. Do not use `<ul>`, `<ol>`, or `<li>`, and do not put a bullet dot before the text. The leading label (for example `项目背景：` or `Background:`) renders bold so the point structure is visible at a glance.

## 3. Thin projects, packaging proposals, and build mode

- 内容太少的项目做不出效果。多问约束、决策、取舍、产物和反馈，找出真实亮点；实在填不满一个分点，就去掉这个项目。
- 项目偏小或偏浅时，先做 **项目包装**：归类项目，总结同类项目通常需要的框架、数据、评估、部署和难点，找出缺的部分，提出合理的技术点请用户确认。可以建议用户没提到的合理技术点，但要经用户确认后才写入。
- 项目太薄时问用户：删掉，还是补齐框架、方案和结果做扎实。补齐就是逐条问清缺的内容，再写成完整版本。这就是正常的内容工作。
- 项目包装可以提出合理的技术、方法和改进点给用户确认。确认过的合理内容可以写入，哪怕用户一开始没提到；未确认的不写。
- 学生/实习简历项目偏少时，直接问清真实任务、决策、范围、产物和反馈，把真实贡献写得更充分。这是正常的项目包装，不编造项目、公司、数字或日期，也不用专门声明。
- 如果仍然挖不出第二个亮点，再考虑 build mode。

## 4. Data and honesty

- If no outcome exists, ask for a smaller true detail instead of padding the resume.
- Data is mandatory wherever it strengthens the story: every result-oriented point should carry a number, scope, ratio, time saved, or measurable change. **Ask the user for the real data first** — that is always the first option. Only when the user explicitly chooses "no data" / "I don't know" may you propose one or two plausible candidate values, explain the assumption, and ask the user to confirm the value is reasonable before writing it. A confirmed candidate is recorded as user-asserted, not verified; an unconfirmed candidate stays out.
- Never jump to invented numbers while real data may exist. The fallback order is: ask for real data → if unavailable, ask permission to estimate → propose candidate values → user confirms → write.
- When the user says there is no number, ask whether to package the existing work with a stronger narrative; "keep it as is" and "skip" are not equivalent choices. Packaging may reorder and sharpen real work, never add a metric.

## 5. Structure and dates

- Never let a bare label render alone (for example, a degree with no other detail). Education writes `major · degree` on the entry line; GPA/rank goes below when present.
- Final dates are concrete `YYYY.MM`. Flag `至今` / `present` and ask for a concrete end month before delivery.

## 6. Merged projects

- When the user has related projects (for example an application and a tool/skill), merge them into one integrated project: let the application's agent call the tool so the story covers data, matching, and optimization in one system. Confirm the integration with the user first.
- Describe only the difficulty and key points of a merged project; keep it appropriately detailed, not a feature dump. Lead with the integrated capability and the hardest problem it solves.
- If a component is open-sourced, state that as a concrete result rather than leaving it implied.