/* Evidence-time helpers. Inputs to atOrBefore are in recorded chronological
 * order; equal timestamps preserve the original event order. No interpolation
 * or wall/simulation clock conversion takes place here.
 */
(() => {
  'use strict';

  function atOrBefore(items, time, key = 'sim_time_s') {
    if (!Array.isArray(items) || !Number.isFinite(time)) return null;
    let lo = 0, hi = items.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (items[mid][key] <= time) lo = mid + 1;
      else hi = mid;
    }
    return items[lo - 1] || null;
  }

  function availableOutput(call, time) {
    // A stale reply can be inspected with its stale label. A reply logged after
    // the physical endpoint cannot become in-run output merely because the
    // stopped simulation clock equals the endpoint's timestamp.
    return Boolean(call?.output_ref && Number.isFinite(time)
      && Number.isFinite(call.request_sim_time_s)
      && Number.isFinite(call.response_sim_time_s)
      && call.request_sim_time_s <= time
      && call.response_sim_time_s >= call.request_sim_time_s
      && call.response_sim_time_s <= time
      && !call.after_episode_end
      && !call.request_after_physical_end
      && !call.response_after_physical_end);
  }

  function withinPhysicalEnd(eventOrRow, endId, eventIdKey = 'event_id') {
    const id = eventOrRow?.[eventIdKey];
    return Number.isFinite(id) && Number.isFinite(endId) && id <= endId;
  }

  const timeline = Object.freeze({atOrBefore, availableOutput, withinPhysicalEnd});
  globalThis.ExplorerTimeline = timeline;
  if (typeof module !== 'undefined' && module.exports) module.exports = timeline;
})();
