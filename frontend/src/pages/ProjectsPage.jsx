import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FolderKanban, Loader2, Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { createProject, deleteProject, getProjects } from "../lib/api";
import { useI18n } from "../lib/i18n.jsx";

/** Projects: create one, then open it to say what it looks for. */
export default function ProjectsPage() {
  const { t } = useI18n();
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setProjects(await getProjects());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createProject({ name: name.trim(), description: description.trim() || null });
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const remove = async (project) => {
    if (!window.confirm(t("projects.confirm.deleteProject").replace("{name}", project.name)))
      return;
    try {
      await deleteProject(project.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderKanban className="h-5 w-5" />
            {t("projects.title")}
          </CardTitle>
          <CardDescription>{t("projects.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-wrap items-end gap-3" onSubmit={create}>
            <label className="space-y-1">
              <span className="block text-sm font-medium">{t("projects.field.projectName")}</span>
              <Input
                className="w-64"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("projects.field.projectName.placeholder")}
              />
            </label>
            <label className="min-w-64 flex-1 space-y-1">
              <span className="block text-sm font-medium">{t("projects.field.description")}</span>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <Button type="submit" disabled={creating || !name.trim()}>
              {creating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {t("projects.create")}
            </Button>
          </form>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {projects === null && !error && (
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      )}
      {projects?.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("projects.none")}</p>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects?.map((p) => (
          <Card key={p.id}>
            <CardHeader>
              <div className="flex items-start gap-2">
                <CardTitle className="flex-1">
                  <Link to={`/projects/${p.id}`} className="hover:underline">
                    {p.name}
                  </Link>
                </CardTitle>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={t("projects.delete")}
                  onClick={() => remove(p)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              {p.description && <CardDescription>{p.description}</CardDescription>}
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                <Badge>
                  {p.entities} {t("projects.kind.entities").toLowerCase()}
                </Badge>
                <Badge>
                  {p.relations} {t("projects.kind.relations").toLowerCase()}
                </Badge>
                <Badge>
                  {p.classifications} {t("projects.kind.classifications").toLowerCase()}
                </Badge>
                <Badge>
                  {p.safety_checks} {t("projects.kind.safety").toLowerCase()}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {p.created_by} · {new Date(p.created_at).toLocaleDateString()}
              </p>
              <Link
                to={`/projects/${p.id}`}
                className="text-sm font-medium text-primary hover:underline"
              >
                {t("projects.open")} →
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
