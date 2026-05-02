"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  Download,
  Package,
  Power,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  deleteLocalSkill,
  fetchLocalSkills,
  fetchMarketSkills,
  fetchSkillMarketSources,
  installMarketSkill,
  setLocalSkillEnabled,
  type MarketSkill,
  type SkillMarketSource,
  type SkillSummary,
} from "@/lib/api";

interface SkillsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type SkillTab = "market" | "installed";
type SelectedSkill =
  | { kind: "market"; skill: MarketSkill }
  | { kind: "installed"; skill: SkillSummary };

const FALLBACK_SOURCES: SkillMarketSource[] = [
  {
    id: "claude-code-skills",
    name: "claude-code-skills",
    url: "https://raw.githubusercontent.com/alirezarezvani/claude-skills/main/marketplace.json",
  },
  {
    id: "daymade-skills",
    name: "daymade-skills",
    url: "https://raw.githubusercontent.com/daymade/claude-code-skills/main/marketplace.json",
  },
];

function getInitial(name: string): string {
  return (name.trim()[0] || "S").toUpperCase();
}

function capabilityTags(skill: MarketSkill | SkillSummary): string[] {
  if (skill.capabilities?.length) {
    return skill.capabilities;
  }

  const allowedTools = skill.allowed_tools || "";
  const tags: string[] = [];
  const toolMap = [
    ["Read", "文件读取"],
    ["Write", "文件写入"],
    ["Edit", "文件编辑"],
    ["Bash", "命令执行"],
    ["WebFetch", "网络请求"],
    ["WebSearch", "网络搜索"],
  ];
  for (const [token, label] of toolMap) {
    if (allowedTools.includes(token)) {
      tags.push(label);
    }
  }
  return tags.length ? tags : ["本地技能"];
}

function matchesQuery(skill: MarketSkill | SkillSummary, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [skill.name, skill.description, skill.version, skill.author]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

export function SkillsPanel({ isOpen, onClose }: SkillsPanelProps) {
  const [activeTab, setActiveTab] = useState<SkillTab>("market");
  const [query, setQuery] = useState("");
  const [marketSourceId, setMarketSourceId] = useState(FALLBACK_SOURCES[0].id);
  const [marketSources, setMarketSources] = useState<SkillMarketSource[]>(FALLBACK_SOURCES);
  const [marketSkills, setMarketSkills] = useState<MarketSkill[]>([]);
  const [installedSkills, setInstalledSkills] = useState<SkillSummary[]>([]);
  const [selected, setSelected] = useState<SelectedSkill | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMarketLoading, setIsMarketLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [confirmDeletePath, setConfirmDeletePath] = useState<string | null>(null);

  const installedIds = useMemo(
    () => new Set(installedSkills.flatMap((skill) => [skill.id, skill.name, skill.path.split("/")[0]])),
    [installedSkills],
  );

  const visibleMarketSkills = useMemo(
    () => marketSkills.filter((skill) => matchesQuery(skill, query)),
    [marketSkills, query],
  );

  const visibleInstalledSkills = useMemo(
    () => installedSkills.filter((skill) => matchesQuery(skill, query)),
    [installedSkills, query],
  );

  const visibleSkills = activeTab === "market" ? visibleMarketSkills : visibleInstalledSkills;

  const loadInstalledSkills = useCallback(async () => {
    const installed = await fetchLocalSkills();
    setInstalledSkills(installed);
    return installed;
  }, []);

  const loadMarketSkills = useCallback(async (sourceId: string, preferredSelectedId?: string | null) => {
    setIsMarketLoading(true);
    setError("");
    try {
      const market = await fetchMarketSkills(sourceId);
      setMarketSkills(market);
      setSelected((prev) => {
        if (activeTab !== "market") {
          return prev;
        }
        const selectedId = preferredSelectedId ?? (prev?.kind === "market" ? prev.skill.id : null);
        const next = selectedId ? market.find((skill) => skill.id === selectedId) : market[0];
        return next ? { kind: "market", skill: next } : null;
      });
    } catch (loadError) {
      console.error("Failed to load market skills:", loadError);
      setMarketSkills([]);
      if (activeTab === "market") {
        setSelected(null);
        setError("无法连接到技能源，请切换源或稍后重试。");
      }
    } finally {
      setIsMarketLoading(false);
    }
  }, [activeTab]);

  const loadSkills = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [sources, installed] = await Promise.all([
        fetchSkillMarketSources().catch(() => FALLBACK_SOURCES),
        loadInstalledSkills(),
      ]);
      setMarketSources(sources);
      const nextSourceId = sources.some((source) => source.id === marketSourceId)
        ? marketSourceId
        : sources[0]?.id ?? FALLBACK_SOURCES[0].id;
      setMarketSourceId(nextSourceId);
      await loadMarketSkills(nextSourceId);

      if (activeTab === "installed") {
        setSelected((prev) => {
          const nextInstalled = prev?.kind === "installed"
            ? installed.find((skill) => skill.path === prev.skill.path)
            : installed[0];
          return nextInstalled ? { kind: "installed", skill: nextInstalled } : null;
        });
      }
    } catch (loadError) {
      console.error("Failed to load skills:", loadError);
      setError("技能列表加载失败，请确认后端服务已重启。");
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, loadInstalledSkills, loadMarketSkills, marketSourceId]);

  const selectTab = (tab: SkillTab) => {
    setActiveTab(tab);
    setQuery("");
    setConfirmDeletePath(null);
    setSuccessMessage("");
    const first = tab === "market" ? marketSkills[0] : installedSkills[0];
    setSelected(first ? { kind: tab, skill: first as never } : null);
  };

  const handleSourceChange = async (sourceId: string) => {
    setMarketSourceId(sourceId);
    setQuery("");
    setConfirmDeletePath(null);
    setSuccessMessage("");
    await loadMarketSkills(sourceId);
  };

  const handleInstall = async (skill: MarketSkill) => {
    if (installedIds.has(skill.id)) {
      return;
    }
    setBusyId(skill.id);
    setError("");
    setSuccessMessage("");
    try {
      const installed = await installMarketSkill(skill.id, skill.source_id || marketSourceId);
      await loadInstalledSkills();
      setSelected({ kind: "market", skill });
      setSuccessMessage(`已安装 ${installed.skill.name}`);
    } catch (installError) {
      console.error("Failed to install skill:", installError);
      setError("安装失败，技能可能已经安装或技能源暂时不可用。");
      await loadInstalledSkills().catch(() => undefined);
    } finally {
      setBusyId(null);
    }
  };

  const handleToggle = async (skill: SkillSummary, enabled: boolean) => {
    setBusyId(skill.path);
    setError("");
    setSuccessMessage("");
    try {
      const updated = await setLocalSkillEnabled(skill.path, enabled);
      setInstalledSkills((prev) =>
        prev.map((item) => (item.path === updated.path ? updated : item)),
      );
      setSelected({ kind: "installed", skill: updated });
    } catch (toggleError) {
      console.error("Failed to update skill:", toggleError);
      setError("状态更新失败，请稍后重试。");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (skill: SkillSummary) => {
    if (confirmDeletePath !== skill.path) {
      setConfirmDeletePath(skill.path);
      return;
    }

    setBusyId(skill.path);
    setError("");
    setSuccessMessage("");
    try {
      await deleteLocalSkill(skill.path);
      const remaining = installedSkills.filter((item) => item.path !== skill.path);
      setInstalledSkills(remaining);
      setConfirmDeletePath(null);
      const next = remaining[0];
      setSelected(next ? { kind: "installed", skill: next } : null);
    } catch (deleteError) {
      console.error("Failed to delete skill:", deleteError);
      setError("删除失败，请稍后重试。");
    } finally {
      setBusyId(null);
    }
  };

  useEffect(() => {
    if (isOpen) {
      void loadSkills();
    }
  }, [isOpen, loadSkills]);

  if (!isOpen) return null;

  const detailSkill = selected?.skill ?? null;
  const selectedMarketSkill = selected?.kind === "market" ? selected.skill : null;
  const selectedInstalledSkill = selected?.kind === "installed" ? selected.skill : null;
  const isSelectedInstalled = selectedMarketSkill ? installedIds.has(selectedMarketSkill.id) : false;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="relative flex h-[82vh] w-full max-w-5xl overflow-hidden rounded-xl bg-background shadow-2xl">
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="absolute right-3 top-3 z-10 h-8 w-8"
        >
          <X className="h-4 w-4" />
        </Button>

        <aside className="flex w-[360px] flex-col border-r border-gray-200 bg-muted/30">
          <div className="border-b border-gray-200 p-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              <h2 className="font-semibold">技能</h2>
            </div>

            <div className="mt-4 grid grid-cols-2 rounded-md border border-gray-200 bg-background p-1">
              <button
                type="button"
                onClick={() => selectTab("market")}
                className={cn(
                  "rounded px-3 py-1.5 text-sm font-medium transition-colors",
                  activeTab === "market"
                    ? "bg-muted text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                技能市场
              </button>
              <button
                type="button"
                onClick={() => selectTab("installed")}
                className={cn(
                  "rounded px-3 py-1.5 text-sm font-medium transition-colors",
                  activeTab === "installed"
                    ? "bg-muted text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                已安装
              </button>
            </div>

            {activeTab === "market" && (
              <Select value={marketSourceId} onValueChange={(value) => void handleSourceChange(value)}>
                <SelectTrigger className="mt-3 h-9 border-gray-200 text-sm focus:ring-primary">
                  <SelectValue placeholder="选择技能源" />
                </SelectTrigger>
                <SelectContent>
                  {marketSources.map((source) => (
                    <SelectItem key={source.id} value={source.id}>
                      {source.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <div className="relative mt-3">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={activeTab === "market" ? "搜索市场技能" : "搜索已安装技能"}
                className="pl-8 placeholder:text-muted-foreground/60 focus-visible:border-primary"
              />
            </div>
          </div>

          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-2 p-3">
              {(isLoading || (activeTab === "market" && isMarketLoading)) && (
                <div className="flex items-center gap-2 rounded-lg px-3 py-3 text-sm text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  加载中
                </div>
              )}

              {!isLoading && !(activeTab === "market" && isMarketLoading) && visibleSkills.length === 0 && (
                <div className="rounded-lg px-3 py-10 text-center text-sm text-muted-foreground">
                  {error || (activeTab === "market" ? "没有可安装技能" : "暂无已安装技能")}
                </div>
              )}

              {activeTab === "market" &&
                !isMarketLoading &&
                visibleMarketSkills.map((skill) => {
                  const installed = installedIds.has(skill.id);
                  const installing = busyId === skill.id;
                  const selectedNow =
                    selected?.kind === "market" && selected.skill.id === skill.id;
                  return (
                    <div
                      key={skill.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        setConfirmDeletePath(null);
                        setSelected({ kind: "market", skill });
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          setConfirmDeletePath(null);
                          setSelected({ kind: "market", skill });
                        }
                      }}
                      className={cn(
                        "grid w-full grid-cols-[36px_minmax(0,1fr)_64px] items-center gap-3 rounded-lg border border-l-2 bg-background px-3 py-3 text-left transition-colors hover:bg-muted/40",
                        selectedNow
                          ? "border-gray-200 border-l-primary bg-muted/50 shadow-sm"
                          : "border-gray-200 border-l-transparent",
                      )}
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-sm font-semibold text-primary">
                        {getInitial(skill.name)}
                      </div>
                      <div className="min-w-0 flex-1 overflow-hidden">
                        <div className="truncate text-sm font-medium leading-5">{skill.name}</div>
                        <div className="overflow-hidden text-ellipsis whitespace-nowrap text-xs leading-4 text-muted-foreground">
                          {skill.description || "暂无简介"}
                        </div>
                      </div>
                      {installed ? (
                        <Badge
                          variant="secondary"
                          className="justify-center px-1 py-0 text-xs font-medium"
                        >
                          已安装
                        </Badge>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          disabled={installing}
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleInstall(skill);
                          }}
                        >
                          {installing ? "安装中..." : "安装"}
                        </Button>
                      )}
                    </div>
                  );
                })}

              {activeTab === "installed" &&
                visibleInstalledSkills.map((skill) => {
                  const selectedNow =
                    selected?.kind === "installed" && selected.skill.path === skill.path;
                  return (
                    <button
                      key={skill.path}
                      type="button"
                      onClick={() => {
                        setConfirmDeletePath(null);
                        setSelected({ kind: "installed", skill });
                      }}
                      className={cn(
                        "grid w-full grid-cols-[36px_minmax(0,1fr)_44px] items-center gap-3 rounded-lg border border-l-2 bg-background px-3 py-3 text-left transition-colors hover:bg-muted/40",
                        selectedNow
                          ? "border-gray-200 border-l-primary bg-muted/50 shadow-sm"
                          : "border-gray-200 border-l-transparent",
                      )}
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted text-sm font-semibold">
                        {getInitial(skill.name)}
                      </div>
                      <div className="min-w-0 flex-1 overflow-hidden">
                        <div className="truncate text-sm font-medium leading-5">{skill.name}</div>
                        <div className="overflow-hidden text-ellipsis whitespace-nowrap text-xs leading-4 text-muted-foreground">
                          {skill.description || skill.path}
                        </div>
                      </div>
                      <Badge
                        variant={skill.enabled ? "secondary" : "outline"}
                        className="justify-center px-1 py-0 text-xs font-medium"
                      >
                        {skill.enabled ? "启用" : "禁用"}
                      </Badge>
                    </button>
                  );
                })}
            </div>
          </ScrollArea>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col bg-background">
          {detailSkill ? (
            <>
              <div className="border-b border-gray-200 bg-muted/20 p-6">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-xl font-semibold text-primary">
                    {getInitial(detailSkill.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-lg font-semibold leading-6">{detailSkill.name}</h3>
                      <Badge variant="secondary" className="shrink-0 text-xs font-medium">
                        v{detailSkill.version}
                      </Badge>
                    </div>
                    <div className="mt-1 text-xs font-normal leading-4 text-muted-foreground">
                      作者：{detailSkill.author || "Unknown"}
                    </div>
                  </div>
                </div>
              </div>

              <ScrollArea className="min-h-0 flex-1">
                <div className="max-w-3xl space-y-5 p-6">
                  <section>
                    <h4 className="text-sm font-medium">简介</h4>
                    <p className="mt-2 line-clamp-4 text-sm font-normal leading-6 text-muted-foreground">
                      {detailSkill.description || "这个技能还没有简介。"}
                    </p>
                  </section>

                  <Separator className="bg-gray-200" />

                  <section>
                    <h4 className="text-sm font-medium">能力 / 权限</h4>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {capabilityTags(detailSkill).map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs font-medium">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </section>
                </div>
              </ScrollArea>

              <div className="mt-auto border-t border-gray-200 bg-muted/20 p-4">
                {selectedMarketSkill ? (
                  <div className="flex items-center justify-between gap-4">
                    <div className="text-xs text-muted-foreground">
                      {successMessage}
                    </div>
                    <Button
                      onClick={() => void handleInstall(selectedMarketSkill)}
                      disabled={isSelectedInstalled || busyId === selectedMarketSkill.id}
                      variant={isSelectedInstalled ? "secondary" : "default"}
                      className="gap-2"
                    >
                      {isSelectedInstalled ? (
                        <Check className="h-4 w-4" />
                      ) : busyId === selectedMarketSkill.id ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                      {isSelectedInstalled ? "已安装" : busyId === selectedMarketSkill.id ? "安装中..." : "安装"}
                    </Button>
                  </div>
                ) : selectedInstalledSkill ? (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <Power className="h-4 w-4 text-muted-foreground" />
                        <div className="text-sm font-medium leading-5">启用技能</div>
                        <Switch
                          checked={selectedInstalledSkill.enabled}
                          disabled={busyId === selectedInstalledSkill.path}
                          onCheckedChange={(checked) => void handleToggle(selectedInstalledSkill, checked)}
                          className="h-6 w-11"
                        />
                      </div>
                      <Button
                        variant={confirmDeletePath === selectedInstalledSkill.path ? "destructive" : "outline"}
                        onClick={() => void handleDelete(selectedInstalledSkill)}
                        disabled={busyId === selectedInstalledSkill.path}
                        className={cn(
                          "h-8 gap-2",
                          confirmDeletePath !== selectedInstalledSkill.path &&
                            "text-destructive hover:text-destructive",
                        )}
                      >
                        {busyId === selectedInstalledSkill.path ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                        {confirmDeletePath === selectedInstalledSkill.path ? "确认删除" : "删除"}
                      </Button>
                    </div>
                    <div className="pl-7 text-xs font-normal leading-4 text-muted-foreground">
                      禁用后不会被 Hermes 加载。
                    </div>
                  </div>
                ) : null}
                {error && <div className="mt-3 text-xs text-destructive">{error}</div>}
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center bg-muted/20">
              <div className="text-center">
                <Package className="mx-auto h-10 w-10 text-muted-foreground" />
                <h3 className="mt-4 text-lg font-medium">选择一个技能</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  在左侧浏览技能市场或管理已安装技能。
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
