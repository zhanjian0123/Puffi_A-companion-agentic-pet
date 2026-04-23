# AI Pet Memory & Skill Notes

更新时间：2026-04-23

## 1. 记忆写入规则（当前实现）

- `SDK session` 负责短期上下文（`AI_PET_SESSION_*`），与长期 Markdown 记忆分开。
- 长期记忆使用 Markdown 文件目录：`data/memory/`。
- 显式写入：用户消息包含 `记住 / 帮我记 / 请记 / 以后要记得` 时，会写入长期记忆。
- 显式删除：用户消息包含 `忘记 / 忘掉 / 不要记住 / 别记住` 时，会在匹配文件中删除对应 bullet。
- 自动捕获：`AI_PET_MEMORY_AUTO_CAPTURE=true` 时，像 `我平常... / 我喜欢... / 我习惯... / 我希望...` 的稳定偏好句会自动写入记忆。
- 自动捕获默认写 `core`；当句子里有 `当前模式 / 这个模式 / 本模式 / 模式下` 时写入当前 mode 记忆。
- 记忆不会再直接把原句写进稳定区，而是先抽取成规范摘要，再写入 `Stable Preferences / Habits / Collaboration Rules` 等稳定区。
- 为了控制 core/mode 文件窗口大小，原始句子不会保存到长期记忆文件。

## 2. core 与 mode 文件位置

- Core：`data/memory/core.md`
- Mode：`data/memory/modes/<mode>.md`（默认 mode 是 `chat`，即 `data/memory/modes/chat.md`）
- Skill 索引：`data/memory/skills/index.md`

Core / Mode 文件只保存稳定摘要：

- Core 稳定区：`Stable Preferences / Habits / Collaboration Rules`
- Mode 稳定区：`Goals / Preferences / Current State`

## 3. Skill 结构与兼容约定

- Skill 文件路径：`data/memory/skills/<skill-name>/SKILL.md`
- Skill 文件采用 `YAML frontmatter + Markdown body`，字段包含 `name / description / version / tags`。
- 该结构用于对齐 OpenAI/Codex、Claude Code、OpenClaw 常见 Skill 组织方式，便于后续迁移和兼容。
- 当前由内置工具 `create_or_update_skill` 生成 Skill 文件。
- 只有用户明确提出“保存为 skill / 沉淀成技能 / 下次复用这个流程”时，才应调用该工具。

## 4. 上下文与文件长度限制

说明：注入上限控制“每次给模型多少内容”；文件上限控制“磁盘里最多保留多少内容”。

- `AI_PET_MEMORY_CORE_CHAR_LIMIT=3000`
- `AI_PET_MEMORY_MODE_CHAR_LIMIT=2500`
- `AI_PET_SKILL_INDEX_CHAR_LIMIT=2000`
- `AI_PET_SKILL_FILE_CHAR_LIMIT=5000`
- `AI_PET_MAX_SKILLS_PER_REQUEST=2`

- `AI_PET_MEMORY_CORE_FILE_MAX_CHARS=12000`
- `AI_PET_MEMORY_MODE_FILE_MAX_CHARS=10000`
- `AI_PET_SKILL_FILE_MAX_CHARS=14000`
- `AI_PET_SKILL_INDEX_FILE_MAX_CHARS=12000`

## 5. 你这类句子的触发说明

示例：`我平常利用codex写代码喜欢先给我方案再进行编码`

- 若 `AI_PET_MEMORY_AUTO_CAPTURE=true`，该句会自动写入 `core.md`。
- 稳定区会写成类似：`编码协作偏好：使用 Codex 写代码时，偏好先给方案，再进行编码。`
- 若希望进入 `chat.md`，需要在句子中明确 mode 语义（例如“在这个模式下...”），或后续改规则为“默认写当前 mode”。

## 6. 记忆回执

- 纯记忆消息会直接返回确定性回执，不依赖模型自由发挥。
- 示例回执：
- `已记录核心记忆：音乐偏好：偏好流行音乐。`
- `已更新核心记忆：编码协作偏好：使用 Codex 写代码时，偏好先给方案，再进行编码。`
- `核心记忆已存在相同内容：音乐偏好：偏好流行音乐。`

## 7. 排查与验证

- 修改 `.env` 或代码后，重启后端：`npm run dev:python`
- 对话后检查文件是否更新：
- `data/memory/core.md`
- `data/memory/modes/chat.md`
- `data/memory/skills/index.md`
- `data/memory/skills/<skill-name>/SKILL.md`
