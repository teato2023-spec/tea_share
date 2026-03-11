-- 커스텀 키맵 (필요에 따라 추가)
local map = vim.keymap.set

-- 터미널
map("n", "<leader>t", ":terminal<CR>", { desc = "터미널 열기" })
map("t", "<Esc>", "<C-\\><C-n>:q<CR>", { desc = "터미널 닫기" })

-- 빠른 설정 파일 열기
map("n", "<leader>oc", ":e ~/.config/nvim/init.lua<CR>", { desc = "init.lua 열기" })

-- Lua 실행
map("n", "<leader>lr", ":luafile %<CR>", { desc = "현재 lua 파일 실행" })
map("n", "<leader>lm", ":messages<CR>",  { desc = "출력 결과 보기" })
