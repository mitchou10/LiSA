import { useMemo, useState } from "react";
import { FileText, Braces, Play } from "lucide-react";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import Results from "../Results";
import { mockAnalyze } from "../lib/mockApi";
import { submitTask } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

const USER_ID = "web-user";

export default function AnalyzePage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("text");
  const [text, setText] = useState("");
  const [json, setJson] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [task, setTask] = useState(null);

  const currentValue = useMemo(() => {
    if (tab === "json") return json;
    return text;
  }, [tab, text, json]);

  const canAnalyze = currentValue.trim().length > 0 && !loading;

  const buildPayload = () => {
    if (tab === "json") {
      const parsed = JSON.parse(json); // throws if invalid
      return typeof parsed === "string" ? parsed : JSON.stringify(parsed);
    }
    return currentValue;
  };

  const analyze = async () => {
    setError(null);
    setResult(null);
    setTask(null);
    let payload;
    try {
      payload = buildPayload();
    } catch {
      setError(t("analyze.error.json"));
      return;
    }
    setLoading(true);
    try {
      // Create a real task on the backend.
      const created = await submitTask({
        userId: USER_ID,
        inputData: { kind: tab, content: payload },
      });
      setTask(created);
      // Fixed/mock scanner results for now.
      const res = await mockAnalyze(payload);
      setResult(res);
    } catch (err) {
      setError(err.message || t("analyze.error.generic"));
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canAnalyze) {
      analyze();
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Left: input */}
      <Card>
        <CardHeader>
          <CardTitle>{t("analyze.input.title")}</CardTitle>
          <CardDescription>{t("analyze.input.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="w-full">
              <TabsTrigger value="text" className="flex-1">
                <FileText className="h-4 w-4" /> {t("analyze.tab.text")}
              </TabsTrigger>
              <TabsTrigger value="json" className="flex-1">
                <Braces className="h-4 w-4" /> {t("analyze.tab.json")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="text">
              <Textarea
                rows={12}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={t("analyze.text.placeholder")}
                className="font-sans"
              />
            </TabsContent>

            <TabsContent value="json">
              <Textarea
                rows={12}
                value={json}
                onChange={(e) => setJson(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={'{\n  "prompt": "ignore all previous instructions"\n}'}
              />
            </TabsContent>
          </Tabs>

          <div className="mt-4 flex items-center gap-3">
            <Button onClick={analyze} disabled={!canAnalyze}>
              <Play className="h-4 w-4" />
              {loading ? t("analyze.running") : t("analyze.run")}
            </Button>
            <span className="text-xs text-muted-foreground">
              {t("analyze.shortcut")}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Right: results */}
      <Card>
        <CardHeader>
          <CardTitle>{t("analyze.results.title")}</CardTitle>
          <CardDescription>{t("analyze.results.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          {task && (
            <div className="mb-4 rounded-lg border border-border bg-background/40 p-3 text-xs">
              <div className="mb-1 font-medium text-success">
                {t("task.created")}
              </div>
              <div className="flex flex-col gap-0.5 text-muted-foreground">
                <span>
                  {t("task.id")} :{" "}
                  <code className="text-foreground">{task.id}</code>
                </span>
                <span>
                  {t("task.status")} :{" "}
                  <code className="text-foreground">{task.status}</code>
                </span>
              </div>
            </div>
          )}
          <Results result={result} loading={loading} error={error} />
        </CardContent>
      </Card>
    </div>
  );
}
