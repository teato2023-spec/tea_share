-- 전역 키맵 (플러그인 무관)
local map = vim.keymap.set

-- 기본 이동
map("n", "<C-h>", "<C-w>h", { desc = "왼쪽 창으로" })
map("n", "<C-l>", "<C-w>l", { desc = "오른쪽 창으로" })
map("n", "<C-j>", "<C-w>j", { desc = "아래 창으로" })
map("n", "<C-k>", "<C-w>k", { desc = "위 창으로" })

-- 창 크기 조절
map("n", "<C-Up>", ":resize +2<CR>", { desc = "창 높이 증가" })
map("n", "<C-Down>", ":resize -2<CR>", { desc = "창 높이 감소" })
map("n", "<C-Left>", ":vertical resize -2<CR>", { desc = "창 너비 감소" })
map("n", "<C-Right>", ":vertical resize +2<CR>", { desc = "창 너비 증가" })

-- 들여쓰기 유지
map("v", "<", "<gv")
map("v", ">", ">gv")

-- 줄 이동
map("v", "J", ":m '>+1<CR>gv=gv", { desc = "선택 줄 아래로" })
map("v", "K", ":m '<-2<CR>gv=gv", { desc = "선택 줄 위로" })

-- 검색 하이라이트 해제
map("n", "<Esc>", ":nohlsearch<CR>", { desc = "검색 강조 해제" })

-- Insert 모드 탈출 시 영어 IME로 자동 전환 (WSL2 전용)
if vim.fn.has("wsl") == 1 then
  vim.api.nvim_create_autocmd("InsertLeave", {
    callback = function()
      vim.fn.jobstart({
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", vim.fn.expand("~/bin/ime-to-en.ps1")
      })
    end,
  })
end

-- 저장 / 종료
map("n", "<leader>w", ":w<CR>", { desc = "저장" })
map("n", "<leader>q", ":q<CR>", { desc = "종료" })

-- Python 저장 후 실행 (F5)
map("n", "<F5>", ":w<CR>:split | terminal python3 %<CR>", { desc = "Python 저장 후 실행" })

-- 터미널 창에서 Esc → 창 닫기
map("t", "<Esc>", "<C-\\><C-n>:q<CR>", { desc = "터미널 닫기" })

-- 플러그인별 키맵 로드
require("keymaps.nvim-tree")
require("keymaps.nvim-cmp")
require("keymaps.telescope")
require("keymaps.bufferline")
require("keymaps.custom")
