"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PaymentFormDialog } from "./payment-form-dialog";

export function PaymentsToolbar({ students }: { students: Array<{ id: string; full_name: string; student_code: string }> }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="accent" onClick={() => setOpen(true)} disabled={students.length === 0}>
        <Plus className="h-4 w-4" />
        دفعة جديدة
      </Button>
      <PaymentFormDialog students={students} open={open} onOpenChange={setOpen} />
    </>
  );
}
