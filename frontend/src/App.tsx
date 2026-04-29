/**
 * App — Phase 6 toolchain checkpoint.
 *
 * Demonstrates the base UI components: Button, Card, Input, Tabs,
 * Dialog, Toaster. Confirms Tailwind v4 + shadcn-style components +
 * path aliases all work end-to-end. Real pages (Login, Job List, Job
 * Detail, Settings) replace this in subsequent commits.
 */

import { ExternalLink, Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { Input, Label } from "@/components/ui/Input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Toaster, toast } from "@/components/ui/Toaster";

export default function App() {
  const [name, setName] = useState("Shaikh");

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-semibold text-slate-900 tracking-tight">
            Role Tracker
          </h1>
          <p className="mt-2 text-sm uppercase tracking-wider text-slate-500">
            Phase 6 · Component checkpoint
          </p>
        </div>

        {/* Buttons */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Buttons</CardTitle>
              <CardDescription>
                Five variants × four sizes. Hover any of them.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button>Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="destructive">Destructive</Button>
              <Button variant="link">Link</Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm">
                <Sparkles /> Small
              </Button>
              <Button size="md">
                <Sparkles /> Medium
              </Button>
              <Button size="lg">
                <Sparkles /> Large
              </Button>
              <Button size="icon" variant="secondary">
                <Sparkles />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Input */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Form fields</CardTitle>
              <CardDescription>
                Input with focus ring, Textarea, and Label.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="name" className="mb-1.5">
                Your name
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Type something…"
              />
            </div>
            <Button onClick={() => toast.success(`Hello, ${name || "stranger"}!`)}>
              Trigger toast
            </Button>
          </CardContent>
        </Card>

        {/* Tabs */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Tabs</CardTitle>
              <CardDescription>
                Underline style. Active tab gets a 2px indigo border.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="unapplied">
              <TabsList>
                <TabsTrigger value="unapplied">
                  Unapplied <span className="ml-1 text-slate-400 font-normal">7</span>
                </TabsTrigger>
                <TabsTrigger value="all">
                  All <span className="ml-1 text-slate-400 font-normal">9</span>
                </TabsTrigger>
                <TabsTrigger value="applied">
                  Applied <span className="ml-1 text-slate-400 font-normal">2</span>
                </TabsTrigger>
              </TabsList>
              <TabsContent value="unapplied" className="text-sm text-slate-600">
                7 unapplied jobs would render here.
              </TabsContent>
              <TabsContent value="all" className="text-sm text-slate-600">
                9 jobs (all states) would render here.
              </TabsContent>
              <TabsContent value="applied" className="text-sm text-slate-600">
                2 applied jobs would render here.
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Dialog */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Dialog</CardTitle>
              <CardDescription>
                Modal with backdrop, ESC-to-close, focus trap.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="secondary">Open dialog</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Regenerate this letter?</DialogTitle>
                  <DialogDescription>
                    This discards the current strategy and starts over.
                    The previous version will still be in your version
                    history.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="secondary">Cancel</Button>
                  <Button onClick={() => toast("Regenerating…")}>
                    Regenerate
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>

        {/* Interactive card */}
        <Card interactive className="cursor-pointer">
          <CardHeader>
            <div>
              <CardTitle>Interactive card</CardTitle>
              <CardDescription>
                Hover me — I lift 2px and the shadow grows.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            This is the same hover-lift behavior the JobCard will use on
            the Job List page.
          </CardContent>
        </Card>

        {/* API docs link */}
        <div className="text-center pt-4">
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 transition-colors"
          >
            Backend API docs
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {/* Mounted once for the whole app */}
      <Toaster />
    </main>
  );
}
