-- telescope 키맵
local map = vim.keymap.set

map("n", "<leader>ff", ":Telescope find_files<CR>", { desc = "파일 찾기" })
map("n", "<leader>fg", ":Telescope live_grep<CR>", { desc = "텍스트 검색" })
map("n", "<leader>fb", ":Telescope buffers<CR>", { desc = "열린 버퍼 목록" })
map("n", "<leader>fh", ":Telescope help_tags<CR>", { desc = "도움말 검색" })
map("n", "<leader>fr", ":Telescope oldfiles<CR>", { desc = "최근 파일" })
map("n", "<leader>fc", ":Telescope colorscheme<CR>", { desc = "컬러 스킴 변경" })
