-- bufferline 키맵
local map = vim.keymap.set

map("n", "<Tab>", ":BufferLineCycleNext<CR>", { desc = "다음 버퍼" })
map("n", "<S-Tab>", ":BufferLineCyclePrev<CR>", { desc = "이전 버퍼" })
map("n", "<leader>x", ":bdelete<CR>", { desc = "버퍼 닫기" })
map("n", "<leader>bo", ":BufferLineCloseOthers<CR>", { desc = "다른 버퍼 모두 닫기" })
