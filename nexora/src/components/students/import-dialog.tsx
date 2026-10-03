"use client";

import { useRef, useState, useTransition } from "react";
import Papa from "papaparse";
import { toast } from "sonner";
import { Upload, FileSpreadsheet, AlertCircle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { bulkImportStudentsAction } from "@/app/(app)/students/actions";

interface ParsedRow {
  fullName: string;
  studentCode: string;
  email?: string;
  phone?: string;
}

export function ImportStudentsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [fileName, setFileName] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleFile(file: File) {
    setParseError(null);
    setFileName(file.name);
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const mapped: ParsedRow[] = [];
        for (const row of results.data) {
          const fullName = row["الاسم"] || row["full_name"] || row["fullName"] || row["name"];
          const studentCode = row["الكود"] || row["student_code"] || row["studentCode"] || row["code"];
          if (!fullName || !studentCode) continue;
          mapped.push({
            fullName: fullName.trim(),
            studentCode: studentCode.trim(),
            email: (row["البريد"] || row["email"] || "").trim() || undefined,
            phone: (row["الهاتف"] || row["phone"] || "").trim() || undefined,
          });
        }
        if (mapped.length === 0) {
          setParseError("لم يتم العثور على أعمدة صالحة. تأكد من وجود عمودي (الاسم) و(الكود) على الأقل.");
        }
        setRows(mapped);
      },
      error: (err) => setParseError(err.message),
    });
  }

  function reset() {
    setRows([]);
    setFileName(null);
    setParseError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function submit() {
    startTransition(async () => {
      const result = await bulkImportStudentsAction(rows);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(`تم استيراد ${result.inserted} طالباً بنجاح${result.skipped ? `، وتعذّر استيراد ${result.skipped}` : ""}`);
      reset();
      onOpenChange(false);
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>استيراد طلاب من ملف CSV</DialogTitle>
          <DialogDescription>يجب أن يحتوي الملف على عمودي الاسم والكود على الأقل (بالعربية أو الإنجليزية).</DialogDescription>
        </DialogHeader>

        <div
          className="flex cursor-pointer flex-col items-center gap-2 rounded-[var(--radius-md)] border-2 border-dashed border-border p-8 text-center transition-colors hover:border-accent"
          onClick={() => inputRef.current?.click()}
        >
          <FileSpreadsheet className="h-8 w-8 text-ink-muted" />
          <p className="text-sm font-medium text-ink">{fileName ?? "اضغط لاختيار ملف CSV"}</p>
          {rows.length > 0 && <p className="text-xs text-success">{rows.length} صف جاهز للاستيراد</p>}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>

        {parseError && (
          <div className="flex items-start gap-2 rounded-[var(--radius-md)] bg-danger-soft px-3 py-2.5 text-xs text-danger">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {parseError}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            إلغاء
          </Button>
          <Button variant="accent" onClick={submit} disabled={rows.length === 0} loading={isPending}>
            <Upload className="h-4 w-4" />
            استيراد {rows.length > 0 ? `(${rows.length})` : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
