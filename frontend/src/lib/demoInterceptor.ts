/**
 * Demo-mode request interceptor.
 *
 * The api.ts request layer asks `tryDemoIntercept(path, options)`
 * before calling fetch. If demo mode is on AND the path matches a
 * known demo endpoint, the interceptor returns a synthetic response
 * (with a small artificial delay so the UI feels real). Otherwise
 * it returns null and api.ts proceeds with the normal fetch.
 *
 * Coverage: every endpoint the frontend can reach in the recruiter
 * tour is handled here — jobs list/detail, manual paste flow, saved
 * queries CRUD, hidden lists, profile, resume metadata + upload,
 * cover-letter generate/refine/polish/edit, polling, downloads,
 * applications, usage, ad-hoc search, snapshot clear. Anything that
 * falls through hits the backend and 401s, which is the signal that
 * a new endpoint was added without a demo handler.
 */

import type { JobDetailResponse } from "@/lib/types";

import {
  DEMO_PROFILE,
  DEMO_USAGE,
  demoAnalysis,
  demoApplications,
  demoAppendLetter,
  demoAppendManualJob,
  demoCreateQuery,
  demoDeleteManualJob,
  demoDeleteQuery,
  demoFetchedJob,
  demoGenerationStatus,
  demoHiddenLists,
  demoJobDetail,
  demoJobList,
  demoLetter,
  demoLetterVersions,
  demoManualJobsList,
  demoMarkApplied,
  demoPolish,
  demoQueriesList,
  demoReplaceResume,
  demoResume,
  demoSetHiddenList,
  demoStartGeneration,
  demoSummary,
  demoUnmarkApplied,
  demoUpdateQuery,
} from "@/lib/demoFixtures";
import { isDemoMode } from "@/lib/demoMode";

interface InterceptOptions {
  method: string;
  json?: unknown;
  formData?: FormData;
}

/** Tracks active fake generation jobs so the polling endpoint can
 *  return progressive phase labels. Keyed by generation_id. */
const ACTIVE_GENERATIONS = new Map<
  string,
  { jobId: string; startedAtMs: number }
>();

const SLEEP_NORMAL = 250; // simulates a fast API call
const SLEEP_SLOW = 500; // simulates a slower one (analysis, summary)

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Top-level dispatch. Returns the synthetic response, or null to
 *  fall through to the real network call. */
export async function tryDemoIntercept<T>(
  path: string,
  options: InterceptOptions,
): Promise<T | null> {
  if (!isDemoMode()) return null;

  // Extract the path-after-/users/{user_id}/ shape — works for
  // both /users/demo/jobs and /users/demo/jobs/x123/letters/2.
  const userMatch = path.match(/^\/users\/[^/]+\/(.+)$/);
  const subpath = userMatch?.[1] ?? null;

  // ----- Health check -----
  if (path === "/health") {
    return { status: "ok", version: "demo" } as unknown as T;
  }

  if (subpath === null) {
    // Anything under /jobs/refresh/{id} that doesn't have user_id —
    // none in this app. Falling through.
    return null;
  }

  // ----- Resume metadata -----
  if (subpath === "resume" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoResume() as unknown as T;
  }
  if (subpath === "resume" && options.method === "POST") {
    // Resume upload (FormData). Read the file's name + size so the
    // settings UI reflects what the recruiter actually picked, then
    // mirror it for subsequent GETs. prefilled_fields stays empty so
    // the profile doesn't get bulk-overwritten.
    await sleep(SLEEP_SLOW);
    const file = options.formData?.get("file");
    const filename =
      file instanceof File ? file.name : null;
    const sizeBytes = file instanceof File ? file.size : null;
    return demoReplaceResume(filename, sizeBytes) as unknown as T;
  }

  // ----- Profile -----
  if (subpath === "profile" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return DEMO_PROFILE as unknown as T;
  }
  if (subpath === "profile" && options.method === "PUT") {
    // Pretend the save worked. Don't actually mutate the fixture.
    await sleep(SLEEP_NORMAL);
    return DEMO_PROFILE as unknown as T;
  }

  // ----- Hidden lists -----
  if (subpath === "hidden" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoHiddenLists() as unknown as T;
  }
  const hiddenPutMatch = subpath.match(
    /^hidden\/(companies|title_keywords|publishers)$/,
  );
  if (hiddenPutMatch && options.method === "PUT") {
    await sleep(SLEEP_NORMAL);
    const body = options.json as { items?: string[] };
    const kind = hiddenPutMatch[1] as
      | "companies"
      | "title_keywords"
      | "publishers";
    return demoSetHiddenList(kind, body?.items ?? []) as unknown as T;
  }

  // ----- Saved queries -----
  if (subpath === "queries" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoQueriesList() as unknown as T;
  }
  if (subpath === "queries" && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    const body = (options.json ?? {}) as { what?: string; where?: string };
    return demoCreateQuery(body) as unknown as T;
  }
  const queryUpdateMatch = subpath.match(/^queries\/([^/]+)$/);
  if (queryUpdateMatch && options.method === "PUT") {
    await sleep(SLEEP_NORMAL);
    const body = (options.json ?? {}) as {
      what?: string;
      where?: string;
      enabled?: boolean;
    };
    const updated = demoUpdateQuery(queryUpdateMatch[1], body);
    if (!updated) throw makeError(404, "Query not found");
    return updated as unknown as T;
  }
  if (queryUpdateMatch && options.method === "DELETE") {
    await sleep(SLEEP_NORMAL);
    demoDeleteQuery(queryUpdateMatch[1]);
    return undefined as unknown as T;
  }

  // ----- Usage dashboard -----
  if (subpath === "usage" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return DEMO_USAGE as unknown as T;
  }

  // ----- Applications list -----
  if (subpath === "applications" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoApplications() as unknown as T;
  }

  // ----- Jobs list -----
  if (subpath === "jobs" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoJobList() as unknown as T;
  }

  // ----- Manually-added jobs (/added-jobs page) -----
  if (subpath === "jobs/manual" && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoManualJobsList() as unknown as T;
  }
  if (subpath === "jobs/manual/fetch" && options.method === "POST") {
    // "Fetch from URL" — preview before saving. The endpoint returns
    // FetchJobUrlResponse (title/company/location/description), not a
    // full JobDetailResponse, so we project from one of the canned
    // manual jobs.
    await sleep(SLEEP_SLOW);
    const j = demoFetchedJob();
    return {
      title: j.title,
      company: j.company,
      location: j.location ?? "",
      description: j.description,
    } as unknown as T;
  }
  if (subpath === "jobs/manual" && options.method === "POST") {
    // "Save the manually-pasted job". Construct a JobDetailResponse
    // from the request body and append it so the list grows on
    // next GET (in-memory only — dies on reload).
    await sleep(SLEEP_NORMAL);
    const body = (options.json ?? {}) as {
      title?: string;
      company?: string;
      description?: string;
      location?: string;
      url?: string;
      salary_min?: number | null;
      salary_max?: number | null;
    };
    const newJob: JobDetailResponse = {
      job_id: `demo-user-manual-${Math.random().toString(36).slice(2, 8)}`,
      title: body.title ?? "Manual job",
      company: body.company ?? "Unknown company",
      location: body.location ?? "",
      posted_at: new Date().toISOString().slice(0, 10),
      salary_min: body.salary_min ?? null,
      salary_max: body.salary_max ?? null,
      publisher: "Manual",
      url: body.url ?? "",
      description: body.description ?? "",
      match_score: 0,
      fit_assessment: null,
      applied: false,
    };
    demoAppendManualJob(newJob);
    return newJob as unknown as T;
  }
  const manualDeleteMatch = subpath.match(/^jobs\/manual\/([^/]+)$/);
  if (manualDeleteMatch && options.method === "DELETE") {
    await sleep(SLEEP_NORMAL);
    demoDeleteManualJob(manualDeleteMatch[1]);
    return undefined as unknown as T;
  }

  // ----- Clear snapshot -----
  if (subpath === "jobs" && options.method === "DELETE") {
    await sleep(SLEEP_NORMAL);
    return undefined as unknown as T;
  }

  // ----- Ad-hoc search (Search now button) -----
  if (subpath === "jobs/search" && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    return {
      search_id: "demo-search",
      status: "pending",
    } as unknown as T;
  }
  const searchStatusMatch = subpath.match(/^jobs\/search\/[^/]+$/);
  if (searchStatusMatch && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return {
      refresh_id: subpath.split("/").pop(),
      status: "done",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      jobs_added: 7,
      candidates_seen: 42,
      queries_run: 1,
      error: null,
    } as unknown as T;
  }

  // ----- Jobs/refresh -----
  if (subpath === "jobs/refresh" && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    return {
      refresh_id: "demo-refresh",
      status: "pending",
    } as unknown as T;
  }
  const refreshMatch = subpath.match(/^jobs\/refresh\/[^/]+$/);
  if (refreshMatch && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return {
      refresh_id: subpath.split("/").pop(),
      status: "done",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      jobs_added: 7,
      candidates_seen: 247,
      queries_run: 3,
      error: null,
    } as unknown as T;
  }

  // ----- Single job detail -----
  const jobDetailMatch = subpath.match(/^jobs\/([^/]+)$/);
  if (jobDetailMatch && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    const job = demoJobDetail(jobDetailMatch[1]);
    if (!job) {
      throw makeError(404, "Job not found");
    }
    return job as unknown as T;
  }

  // ----- JD summary -----
  const summaryMatch = subpath.match(
    /^jobs\/([^/]+)\/cover-letter\/summary$/,
  );
  if (summaryMatch && options.method === "POST") {
    await sleep(SLEEP_SLOW);
    const summary = demoSummary(summaryMatch[1]);
    if (!summary) {
      throw makeError(404, "Job not found");
    }
    return summary as unknown as T;
  }

  // ----- Match analysis -----
  const analysisMatch = subpath.match(
    /^jobs\/([^/]+)\/cover-letter\/analysis$/,
  );
  if (analysisMatch && options.method === "POST") {
    await sleep(SLEEP_SLOW);
    const analysis = demoAnalysis(analysisMatch[1]);
    if (!analysis) {
      throw makeError(404, "Job not found");
    }
    return analysis as unknown as T;
  }

  // ----- Letters list / detail -----
  const lettersListMatch = subpath.match(/^jobs\/([^/]+)\/letters$/);
  if (lettersListMatch && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    return demoLetterVersions(lettersListMatch[1]) as unknown as T;
  }
  const letterDetailMatch = subpath.match(
    /^jobs\/([^/]+)\/letters\/(\d+)$/,
  );
  if (letterDetailMatch && options.method === "GET") {
    await sleep(SLEEP_NORMAL);
    const letter = demoLetter(
      letterDetailMatch[1],
      Number(letterDetailMatch[2]),
    );
    if (!letter) {
      throw makeError(404, "Letter version not found");
    }
    return letter as unknown as T;
  }

  // ----- Generate / Regenerate / Refine — all start a fake job -----
  if (
    lettersListMatch &&
    options.method === "POST"
  ) {
    await sleep(SLEEP_NORMAL);
    const resp = demoStartGeneration();
    ACTIVE_GENERATIONS.set(resp.generation_id, {
      jobId: lettersListMatch[1],
      startedAtMs: Date.now(),
    });
    return resp as unknown as T;
  }
  const regenerateMatch = subpath.match(/^jobs\/([^/]+)\/regenerate$/);
  if (regenerateMatch && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    const resp = demoStartGeneration();
    ACTIVE_GENERATIONS.set(resp.generation_id, {
      jobId: regenerateMatch[1],
      startedAtMs: Date.now(),
    });
    return resp as unknown as T;
  }
  const refineMatch = subpath.match(
    /^jobs\/([^/]+)\/letters\/\d+\/refine$/,
  );
  if (refineMatch && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    const resp = demoStartGeneration();
    ACTIVE_GENERATIONS.set(resp.generation_id, {
      jobId: refineMatch[1],
      startedAtMs: Date.now(),
    });
    return resp as unknown as T;
  }

  // ----- Letter generation polling -----
  const pollMatch = subpath.match(/^letter-jobs\/([^/]+)$/);
  if (pollMatch && options.method === "GET") {
    const generationId = pollMatch[1];
    const tracked = ACTIVE_GENERATIONS.get(generationId);
    if (!tracked) {
      throw makeError(404, "Generation not found");
    }
    await sleep(200); // shorter poll delay
    return demoGenerationStatus(
      tracked.jobId,
      generationId,
      tracked.startedAtMs,
    ) as unknown as T;
  }

  // ----- Manual letter edit (Save edit button) -----
  const editMatch = subpath.match(
    /^jobs\/([^/]+)\/letters\/(\d+)\/edit$/,
  );
  if (editMatch && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    const jobId = editMatch[1];
    const baseVersion = Number(editMatch[2]);
    const body = (options.json ?? {}) as { text?: string };
    const base = demoLetter(jobId, baseVersion);
    const versions = demoLetterVersions(jobId);
    const newVersion = versions.total + 1;
    const text = body.text ?? base?.text ?? "";
    const edited = {
      ...(base ?? ({} as Record<string, unknown>)),
      version: newVersion,
      text,
      word_count: text.split(/\s+/).filter(Boolean).length,
      edited_by_user: true,
      refinement_index: (base?.refinement_index ?? 0) + 1,
      created_at: new Date().toISOString(),
    } as ReturnType<typeof demoLetter>;
    if (edited) demoAppendLetter(jobId, edited);
    return edited as unknown as T;
  }

  // ----- Polish (letter or why-interested) — pass through user text -----
  const polishMatch = subpath.match(
    /^jobs\/[^/]+\/(letters\/\d+\/polish|why-interested\/polish)$/,
  );
  if (polishMatch && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    const body = options.json as { text?: string };
    return demoPolish(body?.text ?? "") as unknown as T;
  }

  // ----- Apply / unapply (toggles in fixture state) -----
  const appliedMatch = subpath.match(/^jobs\/([^/]+)\/applied$/);
  if (appliedMatch && options.method === "POST") {
    await sleep(SLEEP_NORMAL);
    const body = (options.json ?? {}) as {
      letter_version_used?: number | null;
    };
    demoMarkApplied(appliedMatch[1], body.letter_version_used ?? null);
    return { ok: true } as unknown as T;
  }
  if (appliedMatch && options.method === "DELETE") {
    await sleep(SLEEP_NORMAL);
    demoUnmarkApplied(appliedMatch[1]);
    return { ok: true } as unknown as T;
  }

  // ----- Manual edit, save-as-version (chat path) — gated -----
  // These don't need to work in demo; the headline tour doesn't
  // hit them. Fall through (will 401 if anyone reaches them — the
  // UI gates them).

  return null;
}

class DemoApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "DemoApiError";
  }
}

function makeError(status: number, message: string): DemoApiError {
  return new DemoApiError(status, message);
}

/** Returns a synthetic Response for the raw download endpoints
 *  (PDF / DOCX / resume). Used by api.raw() in demo mode. */
export async function tryDemoInterceptRaw(
  path: string,
): Promise<Response | null> {
  if (!isDemoMode()) return null;

  // Letter PDF/DOCX downloads — produce a tiny "demo" placeholder.
  // Real PDF bytes would be ideal but require a build-time asset;
  // for the demo we send a marker file so the download mechanic
  // works end-to-end and the recruiter sees the saved file.
  const letterDownload = path.match(
    /^\/users\/[^/]+\/jobs\/[^/]+\/letters\/(\d+)\/download\.(pdf|docx|md)$/,
  );
  if (letterDownload) {
    await sleep(SLEEP_NORMAL);
    const format = letterDownload[2];
    const text = `Demo cover letter v${letterDownload[1]}\n\n(In live mode this is a real ${format.toUpperCase()} produced from your saved letter.)\n`;
    const blob = new Blob([text], {
      type: format === "md" ? "text/markdown" : "application/octet-stream",
    });
    return new Response(blob, {
      status: 200,
      headers: {
        "Content-Type":
          format === "md" ? "text/markdown" : "application/octet-stream",
        "Content-Disposition": `attachment; filename="demo_letter_v${letterDownload[1]}.${format}"`,
      },
    });
  }

  // Resume download — same idea.
  if (path.match(/^\/users\/[^/]+\/resume\/file$/)) {
    await sleep(SLEEP_NORMAL);
    const text =
      "Demo resume placeholder.\n\n(In live mode this is your uploaded PDF.)";
    const blob = new Blob([text], { type: "application/pdf" });
    return new Response(blob, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'inline; filename="demo_resume.pdf"',
      },
    });
  }

  return null;
}
