-- CodeCompanion (Claude) 키맵
local map = vim.keymap.set

-- ── 채팅 ─────────────────────────────────────────────────────────────────────
map({ "n", "v" }, "<leader>ac", "<cmd>CodeCompanionChat Toggle<CR>",
  { desc = "Claude 채팅 토글" })

map("v", "<leader>as", "<cmd>CodeCompanionChat Add<CR>",
  { desc = "선택 영역을 채팅에 추가" })

-- ── 인라인 어시스트 ──────────────────────────────────────────────────────────
-- 일반 모드: 커서 위치에 코드 생성/수정 지시
map("n", "<leader>ai", "<cmd>CodeCompanion<CR>",
  { desc = "Claude 인라인 어시스트" })

-- 비주얼 모드: 선택 범위를 컨텍스트로 인라인 어시스트
map("v", "<leader>ai", "<cmd>CodeCompanion<CR>",
  { desc = "Claude 인라인 어시스트 (선택)" })

-- ── 액션 팔레트 (자주 쓰는 명령 모음) ──────────────────────────────────────
map({ "n", "v" }, "<leader>aa", "<cmd>CodeCompanionActions<CR>",
  { desc = "Claude 액션 팔레트" })

-- ── 빠른 단축키 ─────────────────────────────────────────────────────────────
-- Ctrl+A: 비주얼 선택 → 채팅 전송
map("v", "<C-a>", "<cmd>CodeCompanionChat Add<CR>",
  { desc = "Claude 채팅에 전송" })
