(function (root) {
  "use strict";
  function identitySummary(rows) {
    const counts = {
      AVAILABLE: 0,
      TAKEN: 0,
      UNKNOWN: 0,
      RATE_LIMITED: 0,
      AUTH_REQUIRED: 0,
      ERROR: 0,
      UNSUPPORTED: 0,
    };
    const original = rows.filter((row) => !row.suggestion);
    for (const row of original)
      if (Object.hasOwn(counts, row.status)) counts[row.status]++;
    return {
      counts,
      available: counts.AVAILABLE,
      conclusive: counts.AVAILABLE + counts.TAKEN,
      unresolved: original.length - counts.AVAILABLE - counts.TAKEN,
      singleUsername:
        new Set(original.map((row) => row.input_username || row.username))
          .size <= 1,
    };
  }
  function filterResults(rows, query, status) {
    const needle = query.toLocaleLowerCase();
    return rows.filter(
      (row) =>
        (!status || row.status === status) &&
        (!needle ||
          (row.platform + " " + row.username)
            .toLocaleLowerCase()
            .includes(needle)),
    );
  }
  root.FeaturesModel = { identitySummary, filterResults };
})(typeof window === "undefined" ? globalThis : window);
