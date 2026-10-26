import { describe, it, expect, beforeEach } from "vitest";

import {
  SAVED_VIEWS_SCHEMA,
  deleteSavedView,
  exportViewsPayload,
  importViews,
  listSavedViews,
  saveView,
} from "../../views/viewStore.js";

const record = (az) => ({ schema: 1, spec: { direction: { azimuthDeg: az, elevationDeg: 20 } }, resolved: { worldAzimuthDeg: az } });

describe("viewStore (localStorage, bi2m:views:<fileKey>)", () => {
  beforeEach(() => localStorage.clear());

  it("stores under bi2m:views:<fileKey> with a schema number", () => {
    saveView("abc", { name: "street", record: record(45) });
    const raw = JSON.parse(localStorage.getItem("bi2m:views:abc"));
    expect(raw.schema).toBe(SAVED_VIEWS_SCHEMA);
    expect(raw.views).toHaveLength(1);
    expect(raw.views[0]).toMatchObject({ name: "street", record: record(45) });
    expect(Date.parse(raw.views[0].savedAt)).not.toBeNaN();
  });
  it("lists oldest first and keeps models apart", () => {
    saveView("abc", { name: "one", record: record(1) });
    saveView("abc", { name: "two", record: record(2) });
    saveView("xyz", { name: "other", record: record(3) });
    expect(listSavedViews("abc").map((v) => v.name)).toEqual(["one", "two"]);
    expect(listSavedViews("xyz").map((v) => v.name)).toEqual(["other"]);
  });
  it("names an unnamed view by its position, like the panel always did", () => {
    saveView("abc", { name: "", record: record(1) });
    saveView("abc", { name: "   ", record: record(2) });
    expect(listSavedViews("abc").map((v) => v.name)).toEqual(["View 1", "View 2"]);
  });
  it("deletes by id, never by name (names may repeat)", () => {
    const a = saveView("abc", { name: "same", record: record(1) });
    saveView("abc", { name: "same", record: record(2) });
    expect(deleteSavedView("abc", a.id)).toBe(true);
    expect(listSavedViews("abc")).toHaveLength(1);
    expect(listSavedViews("abc")[0].record.resolved.worldAzimuthDeg).toBe(2);
    expect(deleteSavedView("abc", "nope")).toBe(false);
  });
  it("export carries the fileKey and round-trips through import", () => {
    saveView("abc", { name: "one", record: record(1) });
    const payload = exportViewsPayload("abc");
    expect(payload).toMatchObject({ schema: SAVED_VIEWS_SCHEMA, fileKey: "abc" });
    expect(payload.views).toHaveLength(1);
    localStorage.clear();
    expect(importViews("abc", payload)).toBe(1);
    expect(listSavedViews("abc")[0]).toEqual(payload.views[0]);
  });
  it("import skips ids already present and refuses entries without a record", () => {
    const a = saveView("abc", { name: "one", record: record(1) });
    const added = importViews("abc", { views: [a, { id: "new", name: "two", record: record(2) }, { id: "bad", name: "no record" }] });
    expect(added).toBe(1);
    expect(listSavedViews("abc").map((v) => v.id)).toEqual([a.id, "new"]);
  });
  it("import with replace empties the store first", () => {
    saveView("abc", { name: "old", record: record(1) });
    importViews("abc", { views: [{ name: "fresh", record: record(2) }] }, { replace: true });
    expect(listSavedViews("abc").map((v) => v.name)).toEqual(["fresh"]);
  });
  it("tolerates corrupt storage", () => {
    localStorage.setItem("bi2m:views:bad", "{not json");
    expect(listSavedViews("bad")).toEqual([]);
    localStorage.setItem("bi2m:views:bad", JSON.stringify({ views: "nope" }));
    expect(listSavedViews("bad")).toEqual([]);
  });
});
