-- 에디터 기본 설정
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 2
vim.opt.shiftwidth = 2
vim.opt.expandtab = true
vim.opt.smartindent = true
vim.opt.wrap = false
vim.opt.termguicolors = true
vim.opt.signcolumn = "yes"
vim.opt.updatetime = 250
vim.opt.clipboard = "unnamedplus"

-- 환경별 클립보드 설정
if vim.fn.has("wsl") == 1 then
  -- WSL2 환경
  vim.g.clipboard = {
    name = "win32yank",
    copy = {
      ["+"] = "/home/tea_02/bin/win32yank.exe -i --crlf",
      ["*"] = "/home/tea_02/bin/win32yank.exe -i --crlf",
    },
    paste = {
      ["+"] = "/home/tea_02/bin/win32yank.exe -o --lf",
      ["*"] = "/home/tea_02/bin/win32yank.exe -o --lf",
    },
    cache_enabled = 0,
  }
end
-- 순수 리눅스는 xclip/xsel 자동 인식 (별도 설정 불필요)
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.scrolloff = 8

vim.g.mapleader = "\\"
vim.g.maplocalleader = "\\"

-- nvim-tree 권장 설정
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1
