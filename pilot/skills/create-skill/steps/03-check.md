## Step 3: Check Existing

```bash
# Project skills
ls .claude/skills/ 2>/dev/null
rg -i "keyword" .claude/skills/ 2>/dev/null
# Global skills (user + Pilot defaults all live at ~/.claude/skills/)
ls ~/.claude/skills/ 2>/dev/null
rg -i "keyword" ~/.claude/skills/ 2>/dev/null
```

| Found | Action |
|-------|--------|
| Nothing related | Create new |
| Same trigger/fix | Update existing (bump version) |
| Partial overlap | Update with new variant |
