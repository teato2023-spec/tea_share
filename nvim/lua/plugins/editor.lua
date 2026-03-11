-- 에디터 플러그인
return {
  -- 문법 강조
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      require("nvim-treesitter").setup()
      -- 미설치 파서만 설치
      local ensure = { "lua", "python", "javascript", "typescript", "bash" }
      local installed = require("nvim-treesitter.config").get_installed()
      local missing = vim.tbl_filter(function(l)
        return not vim.tbl_contains(installed, l)
      end, ensure)
      if #missing > 0 then
        require("nvim-treesitter").install(missing)
      end
    end,
  },

  -- 댓글 토글
  {
    "numToStr/Comment.nvim",
    config = function()
      require("Comment").setup()
    end,
  },

  -- Git 통합
  { "tpope/vim-fugitive" },

  -- Git 변경사항 표시
  {
    "lewis6991/gitsigns.nvim",
    config = function()
      require("gitsigns").setup()
    end,
  },
}
