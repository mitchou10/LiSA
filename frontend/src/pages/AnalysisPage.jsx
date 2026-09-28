import { useState } from "react";
import { FileText, FileUp } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import TextAnalysisTab from "../components/analysis/TextAnalysisTab";
import FileAnalysisTab from "../components/analysis/FileAnalysisTab";
import { useI18n } from "../lib/i18n.jsx";

/**
 * Analysis page: container with tabs for the different input modes
 * (text, file, …). Each tab owns its own analysis engine and results pane,
 * so results are fully independent between tabs.
 */
export default function AnalysisPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("text");

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList className="w-full">
        <TabsTrigger value="text" className="flex-1">
          <FileText className="h-4 w-4" /> {t("analyze.tab.text")}
        </TabsTrigger>
        <TabsTrigger value="file" className="flex-1">
          <FileUp className="h-4 w-4" /> {t("analyze.tab.file")}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="text" className="mt-6">
        <TextAnalysisTab />
      </TabsContent>

      <TabsContent value="file" className="mt-6">
        <FileAnalysisTab />
      </TabsContent>
    </Tabs>
  );
}
