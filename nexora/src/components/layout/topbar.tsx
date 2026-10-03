import { NotificationsBell } from "./notifications-bell";
import { UserMenu } from "./user-menu";
import { CommandPalette } from "./command-palette";

export function Topbar() {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-paper/90 px-4 backdrop-blur sm:px-6">
      <div className="flex-1">
        <CommandPalette />
      </div>
      <NotificationsBell />
      <UserMenu />
    </header>
  );
}
