-- AI 플러그인 (Claude API)
return {
  {
    "olimorris/codecompanion.nvim",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-treesitter/nvim-treesitter",
      -- 마크다운 렌더링 (선택, 없어도 동작)
      { "MeanderingProgrammer/render-markdown.nvim", optional = true },
    },
    opts = {
      -- ── 어댑터: Claude ──────────────────────────────────────────────────
      adapters = {
        claude = function()
          return require("codecompanion.adapters").extend("anthropic", {
            env = {
              -- 셸에서 ANTHROPIC_API_KEY 환경변수로 주입
              api_key = "ANTHROPIC_API_KEY",
            },
            schema = {
              model = {
                default = "claude-sonnet-4-6",
              },
              max_tokens = {
                default = 8096,
              },
            },
          })
        end,
      },

      -- ── 기본 전략: 모든 모드에 Claude 사용 ──────────────────────────────
      strategies = {
        chat   = { adapter = "claude" },
        inline = { adapter = "claude" },
        agent  = { adapter = "claude" },
      },

      -- ── UI 설정 ──────────────────────────────────────────────────────────
      display = {
        diff = {
          enabled = true,
          provider = "mini_diff",   -- 없으면 자동 fallback
        },
        chat = {
          window = {
            layout = "vertical",   -- "vertical" | "horizontal" | "float"
            width  = 0.35,         -- 화면 너비의 35%
          },
          show_token_count = true,
        },
      },
    },
  },
}
