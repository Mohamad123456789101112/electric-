"use client";

import { useState } from "react";
import { Plus, Upload, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StudentFormDialog } from "./student-form-dialog";
import { ImportStudentsDialog } from "./import-dialog";

export function StudentsToolbar({ classes }: { classes: Array<{ id: string; name: string; subject: string }> }) {
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
        <Upload className="h-3.5 w-3.5" />
        استيراد
      </Button>
      <Button variant="outline" size="sm" asChild>
        <a href="/api/students/export" download>
          <Download className="h-3.5 w-3.5" />
          تصدير
        </a>
      </Button>
      <Button variant="accent" size="sm" onClick={() => setCreateOpen(true)}>
        <Plus className="h-3.5 w-3.5" />
        إضافة طالب
      </Button>

      <StudentFormDialog classes={classes} open={createOpen} onOpenChange={setCreateOpen} />
      <ImportStudentsDialog open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}
