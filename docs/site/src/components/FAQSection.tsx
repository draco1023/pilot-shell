import { HelpCircle } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useInView } from "@/hooks/use-in-view";

const faqItems = [
  {
    question: "What do I need to use Pilot Shell?",
    answer:
      "Pilot Shell enhances your AI coding agent \u2014 it doesn\u2019t replace it. You need at least one: Claude Code (Anthropic) requires a Claude subscription (Max 5x or 20x for solo, Team Premium for teams, Enterprise for orgs). Codex CLI (OpenAI) requires an OpenAI API key. You can use either or both \u2014 the installer auto-detects and configures whichever is installed. Both share the same rules, skills, hooks, MCP servers, and Console. Claude Code has full feature coverage; Codex CLI supports all non-bot skills (/spec, /fix, /prd, /benchmark, /setup-rules, /create-skill).",
  },
  {
    question: "Is Pilot Shell enterprise-compliant for data privacy?",
    answer:
      "Yes. Your source code, project files, and development context never leave your machine through Pilot Shell. The only external calls are license validation (daily, license key only) and one-time activation/trial start (machine fingerprint only). No OS info, no version strings, no analytics, no telemetry. Enterprises using Claude Code with their own API key or Anthropic Enterprise subscription can add Pilot Shell without changing their data compliance posture.",
  },
  {
    question: "Does Pilot Shell work with existing projects?",
    answer:
      "Yes \u2014 that's the primary use case. Pilot Shell doesn't scaffold or restructure your code. You install it, run /setup-rules, and it explores your codebase to discover your tech stack, conventions, and patterns. From there, every session has full context about your project. The more complex and established your codebase, the more value Pilot Shell adds \u2014 quality hooks catch regressions, persistent memory preserves decisions across sessions, and /spec plans features against your real architecture.",
  },
  {
    question: "Does Pilot Shell work with any programming language?",
    answer:
      "Pilot Shell's quality hooks (auto-formatting, linting, type checking) currently support Python, TypeScript/JavaScript, and Go out of the box. TDD enforcement, spec-driven development, persistent memory, context optimization, and all rules and standards work with any language. You can add custom hooks for additional languages.",
  },
  {
    question: "Can I use Pilot Shell on multiple projects?",
    answer:
      "Yes. Pilot Shell installs once globally and works across all your projects \u2014 you don\u2019t need to reinstall per project. All tools, rules, commands, and hooks live in ~/.pilot/ and ~/.claude/, available everywhere. Just cd into any project and run claude or codex. Each project can optionally have its own .claude/ rules, custom skills, and MCP servers for project-specific behavior. Run /setup-rules in each project to generate project-specific documentation and standards.",
  },
  {
    question: "Can I add my own rules, commands, skills, and agents?",
    answer:
      "Yes. Create your own in your project\u2019s .claude/ folder \u2014 rules, commands, skills, and agents are all plain markdown files. Your project-level assets load alongside Pilot Shell\u2019s built-in defaults and take precedence when they overlap. /setup-rules auto-discovers your codebase patterns and generates project-specific rules. /create-skill builds reusable skills from any topic interactively. View and manage all extensions on the Console Extensions page. Team plan users can also share extensions via a connected git repository \u2014 push, pull, and compare versions with your team.",
  },
  {
    question: "Can I customize Pilot\u2019s built-in workflows and defaults?",
    answer:
      "Yes \u2014 the Customization feature (available on the Team plan) lets you modify what Pilot Shell auto-installs, not just add alongside it. Tweak the built-in /spec workflow (insert a security-review step, replace the planning template, disable a step you don\u2019t need), adjust existing rules, register additional hooks, add review agents, change which MCP or LSP servers get configured, and override the auto-applied settings.json and claude.json. Source is either a git repo for your team or a local directory for personal use \u2014 no git needed for a one-off tweak. Skill overlays stay pinned to Pilot\u2019s upstream by hash, so when Pilot ships an improvement to a step you replaced, `pilot customize status` flags the drift and `pilot customize diff` shows what changed.",
  },
  {
    question: "Does Pilot Shell send my code or data to external services?",
    answer:
      "No code, files, prompts, project data, or personal information ever leaves your machine through Pilot Shell. All development tools \u2014 code search (Semble), code intelligence (CodeGraph), persistent memory (Console), session state, and quality hooks \u2014 run entirely locally. No OS info, no version strings, no analytics, no telemetry, no heartbeats. Pilot Shell works fully offline between periodic license checks. If you enable the optional Codex companion plugin, adversarial reviews are sent to OpenAI\u2019s API \u2014 this is opt-in and disabled by default. Codex CLI itself routes prompts to OpenAI as part of normal operation.",
  },
  {
    question: "Pilot feels slower after a few weeks — what should I do?",
    answer:
      "Claude Code’s session logs and Pilot’s caches grow over time and can degrade performance. A periodic reset every few weeks restores a clean baseline: (1) Run /logout inside Claude Code. (2) Back up ~/.claude.json, ~/.claude/, and ~/.pilot/ (rename them to .bak copies). (3) Reinstall Pilot Shell with the official installer from pilot-shell.com. (4) Run pilot and sign in to Claude again. Once Pilot is running smoothly, delete the .bak copies.",
  },
  {
    question: "Can I use Pilot Shell inside a Dev Container?",
    answer:
      "Yes. Copy the .devcontainer folder from the Pilot Shell repository into your project, adapt it to your needs (base image, extensions, dependencies), and install Pilot Shell inside the container. Everything works the same \u2014 hooks, rules, MCP servers, persistent memory, and the Console dashboard all run inside the container. This is a great option for teams that want a consistent, reproducible development environment.",
  },
];

const FAQSection = () => {
  const [headerRef, headerInView] = useInView<HTMLDivElement>();
  const [contentRef, contentInView] = useInView<HTMLDivElement>();

  return (
    <section id="faq" className="py-16 lg:py-24 px-4 sm:px-6 relative">
      <div className="max-w-3xl mx-auto">
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

        <div
          ref={headerRef}
          className={`text-center mb-12 ${headerInView ? "animate-fade-in-up" : "opacity-0"}`}
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
              <HelpCircle className="h-5 w-5 text-primary" />
            </div>
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-foreground mb-4">
            FAQ
          </h2>
          <p className="text-muted-foreground text-lg sm:text-xl max-w-3xl mx-auto">
            Common questions about Pilot Shell, data privacy, and compatibility.
          </p>
        </div>

        <div
          ref={contentRef}
          className={`rounded-lg border border-border/50 bg-card overflow-hidden ${contentInView ? "animate-fade-in-up" : "opacity-0"}`}
        >
          <Accordion type="single" collapsible className="px-6">
            {faqItems.map((item, index) => (
              <AccordionItem
                key={index}
                value={`item-${index}`}
                className="border-border/50"
              >
                <AccordionTrigger className="text-left text-foreground hover:text-primary hover:no-underline text-sm sm:text-base py-5">
                  {item.question}
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground text-sm leading-relaxed">
                  {item.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </div>
    </section>
  );
};

export default FAQSection;
