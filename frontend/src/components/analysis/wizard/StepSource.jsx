import { useRef, useState } from "react";
import { FileText, FileUp, UploadCloud, X } from "lucide-react";
import { Textarea } from "../../ui/textarea";
import { cn } from "../../../lib/utils";
import { useI18n } from "../../../lib/i18n.jsx";
import OptionCard from "./OptionCard";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp";

/** Step 1: a text or files, then the content itself. */
export default function StepSource({ source, onSource, text, onText, files, onFiles }) {
  const { t } = useI18n();
  const input = useRef(null);
  const [over, setOver] = useState(false);

  const add = (list) => onFiles([...files, ...list]);
  const remove = (i) => onFiles(files.filter((_, j) => j !== i));

  return (
    <div className="space-y-4" role="radiogroup" aria-label={t("wiz.source.title")}>
      <OptionCard
        icon={FileText}
        title={t("wiz.source.text")}
        desc={t("wiz.source.text.desc")}
        selected={source === "text"}
        onSelect={() => onSource("text")}
      >
        <Textarea
          rows={9}
          value={text}
          onChange={(e) => onText(e.target.value)}
          placeholder={t("run.text.placeholder")}
        />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {t("wiz.source.chars").replace("{n}", text.length)}
        </p>
      </OptionCard>

      <OptionCard
        icon={FileUp}
        title={t("wiz.source.file")}
        desc={t("wiz.source.file.desc")}
        selected={source === "file"}
        onSelect={() => onSource("file")}
      >
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            add([...e.dataTransfer.files]);
          }}
          onClick={() => input.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors",
            over ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground/50"
          )}
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm font-medium">{t("wiz.source.drop")}</p>
          <p className="text-xs text-muted-foreground">{t("wiz.source.formats")}</p>
          <input
            ref={input}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              add([...e.target.files]);
              e.target.value = "";
            }}
          />
        </div>
        {files.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {files.map((f, i) => (
              <li
                key={f.name + f.size + i}
                className="flex items-center gap-2 rounded-md border border-border bg-background/60 px-3 py-1.5 text-sm"
              >
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate">{f.name}</span>
                <span className="text-xs text-muted-foreground">{(f.size / 1024).toFixed(0)} KB</span>
                <button
                  type="button"
                  onClick={() => remove(i)}
                  aria-label={t("wiz.source.remove")}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </OptionCard>
    </div>
  );
}
