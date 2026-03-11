-- nvim-tree 키맵
local map = vim.keymap.set

map("n", "<leader>e", ":NvimTreeToggle<CR>", { desc = "파일 탐색기 토글" })
map("n", "<leader>ef", ":NvimTreeFindFile<CR>", { desc = "현재 파일 탐색기에서 찾기" })
map("n", "<leader>ec", ":NvimTreeCollapse<CR>", { desc = "파일 탐색기 접기" })
