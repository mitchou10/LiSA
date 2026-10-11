import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Pencil, ScanSearch } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import DefinitionsPanel from "../components/projects/DefinitionsPanel";
import { DEFINITION_KINDS, getProject, updateProject } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

/** One project: its details, and what it looks for (one tab per kind). */
export default function ProjectPage() {
  const { t } = useI18n();
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState(DEFINITION_KINDS[0]);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });

  const load = useCallback(async () => {
    try {
      setProject(await getProject(projectId));
    } catch (err) {
      setError(err.status === 404 ? "notfound" : err.message);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (e) => {
    e.preventDefault();
    try {
      setProject(
        await updateProject(projectId, {
          name: form.name.trim(),
          description: form.description.trim() || null,
        })
      );
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  if (error === "notfound")
    return (
      <div className="space-y-3">
        <p className="text-muted-foreground">{t("projects.notFound")}</p>
        <Button variant="outline" onClick={() => navigate("/projects")}>
          <ArrowLeft className="h-4 w-4" />
          {t("projects.back")}
        </Button>
      </div>
    );
  if (!project)
    return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;

  return (
    <div className="space-y-6">
      <Link
        to="/projects"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("projects.back")}
      </Link>

      <Card>
        <CardHeader>
          {editing ? (
            <form className="flex flex-wrap items-end gap-3" onSubmit={save}>
              <Input
                className="w-64"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <Input
                className="min-w-64 flex-1"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
              <Button type="submit" disabled={!form.name.trim()}>
                {t("projects.save")}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
                {t("projects.cancel")}
              </Button>
            </form>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle>{project.name}</CardTitle>
              <Button
                size="icon"
                variant="ghost"
                aria-label={t("projects.edit")}
                onClick={() => {
                  setForm({ name: project.name, description: project.description ?? "" });
                  setEditing(true);
                }}
              >
                <Pencil className="h-4 w-4" />
              </Button>
              <Link to={`/analysis?project=${project.id}`} className="ml-auto">
                <Button size="sm">
                  <ScanSearch className="h-4 w-4" />
                  {t("projects.analyze")}
                </Button>
              </Link>
            </div>
          )}
          {!editing && project.description && (
            <CardDescription>{project.description}</CardDescription>
          )}
        </CardHeader>
        {error && (
          <CardContent>
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        )}
      </Card>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="w-full">
          {DEFINITION_KINDS.map((kind) => (
            <TabsTrigger key={kind} value={kind} className="flex-1">
              {t(`projects.kind.${kind}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        {DEFINITION_KINDS.map((kind) => (
          <TabsContent key={kind} value={kind} className="mt-6">
            <DefinitionsPanel projectId={project.id} kind={kind} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
