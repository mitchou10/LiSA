import { useMemo, useState } from "react";
import { FileText, Braces, Link as LinkIcon, Play } from "lucide-react";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import { Input } from "../components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import Results from "../Results";
import { mockAnalyze } from "../lib/mockApi";

export default function AnalyzePage() {
  const [tab, setTab] = useState("text");
  const [text, setText] = useState("");
  const [json, setJson] = useState("");
  const [url, setUrl] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const currentValue = useMemo(() => {
    if (tab === "text") return text;
    if (tab === "json") return json;
    return url;
  }, [tab, text, json, url]);

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
    let payload;
    try {
      payload = buildPayload();
    } catch {
      setError("JSON invalide. Vérifiez la syntaxe.");
      return;
    }
    if (tab === "url" && !/^https?:\/\/.+/i.test(url.trim())) {
      setError("URL invalide. Elle doit commencer par http:// ou https://");
      return;
    }
    setLoading(true);
    try {
      const res = await mockAnalyze(payload);
      setResult(res);
    } catch (err) {
      setError(err.message || "Une erreur est survenue.");
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
          <CardTitle>Entrée</CardTitle>
          <CardDescription>
            Choisissez un format puis lancez l'analyse (Ctrl/Cmd + Entrée).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="w-full">
              <TabsTrigger value="text" className="flex-1">
                <FileText className="h-4 w-4" /> Texte
              </TabsTrigger>
              <TabsTrigger value="json" className="flex-1">
                <Braces className="h-4 w-4" /> JSON
              </TabsTrigger>
              <TabsTrigger value="url" className="flex-1">
                <LinkIcon className="h-4 w-4" /> URL
              </TabsTrigger>
            </TabsList>

            <TabsContent value="text">
              <Textarea
                rows={12}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Collez ou écrivez le texte à analyser…"
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

            <TabsContent value="url">
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="https://exemple.com/page-a-analyser"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Le contenu de l'URL sera récupéré et analysé (mock).
              </p>
            </TabsContent>
          </Tabs>

          <div className="mt-4 flex items-center gap-3">
            <Button onClick={analyze} disabled={!canAnalyze}>
              <Play className="h-4 w-4" />
              {loading ? "Analyse…" : "Analyser"}
            </Button>
            <span className="text-xs text-muted-foreground">
              Ctrl/Cmd + Entrée
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Right: results */}
      <Card>
        <CardHeader>
          <CardTitle>Résultats</CardTitle>
          <CardDescription>Verdict global et score par scanner.</CardDescription>
        </CardHeader>
        <CardContent>
          <Results result={result} loading={loading} error={error} />
        </CardContent>
      </Card>
    </div>
  );
}
