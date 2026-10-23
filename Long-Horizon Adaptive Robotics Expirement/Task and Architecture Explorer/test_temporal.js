/* Pure evidence-display regressions; no browser, physics, model, or queue work.
 * Run: node "Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/test_temporal.js"
 */
'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const timeline = require('./temporal.js');
const {atOrBefore, availableOutput, withinPhysicalEnd} = timeline;

test('browser and Node use the identical helper object', () => {
  assert.equal(globalThis.ExplorerTimeline, timeline);
});

test('empty and not-yet-observed timelines supply no invented sample', () => {
  assert.equal(atOrBefore([], 0.5), null);
  assert.equal(atOrBefore([{sim_time_s: 0.502}], 0.5), null);
  assert.equal(atOrBefore([{sim_time_s: 0.502}], NaN), null);
  assert.equal(atOrBefore([{sim_time_s: 0.502}], Infinity), null);
});

test('exact boundaries include a record and intervening time holds the prior sample', () => {
  const first = {sim_time_s: 0.502}, second = {sim_time_s: 0.702};
  const samples = [first, second];
  assert.equal(atOrBefore(samples, 0.502), first);
  assert.equal(atOrBefore(samples, 0.701999), first);
  assert.equal(atOrBefore(samples, 0.702), second);
});

test('backward seeks do not retain a previously selected future sample', () => {
  const samples = [{sim_time_s: 1}, {sim_time_s: 2}, {sim_time_s: 3}];
  for (const time of [3, 1.5, 2, 0.9, 1, 2.99]) {
    const selected = atOrBefore(samples, time);
    const expected = samples.filter(row => row.sim_time_s <= time).at(-1) || null;
    assert.equal(selected, expected);
    if (selected) assert.ok(selected.sim_time_s <= time);
  }
});

test('equal-time records preserve the final original record at that timestamp', () => {
  const rows = [{event_id: 8, sim_time_s: 1}, {event_id: 9, sim_time_s: 1}];
  assert.equal(atOrBefore(rows, 1), rows[1]);
});

test('model request lookup uses its simulation timestamp, without wall-time conversion', () => {
  const call = {request_sim_time_s: 0.576, request_wall_elapsed_s: 0.07449};
  assert.equal(atOrBefore([call], 0.1, 'request_sim_time_s'), null);
  assert.equal(atOrBefore([call], 0.575999, 'request_sim_time_s'), null);
  assert.equal(atOrBefore([call], 0.576, 'request_sim_time_s'), call);
});

const response = {
  request_sim_time_s: 0.576, response_sim_time_s: 2.662,
  output_ref: {href: 'data/payloads/example.json'},
  stale: false, after_episode_end: false, response_after_physical_end: false,
};

test('recorded output remains unavailable before the request and throughout inference', () => {
  for (const time of [0.5, 0.575999, 0.576, 2.661999]) {
    assert.equal(availableOutput(response, time), false);
  }
  assert.equal(availableOutput(response, 2.662), true);
});

test('backward seeking hides a response that was previously visible', () => {
  assert.equal(availableOutput(response, 3), true);
  assert.equal(availableOutput(response, 1), false);
  assert.equal(availableOutput(response, 2.662), true);
});

test('stale replies remain inspectable, without implying they were acted upon', () => {
  const stale = {...response, stale: true};
  assert.equal(availableOutput(stale, 2.661999), false);
  assert.equal(availableOutput(stale, 2.662), true);
});

test('late endpoint replies never become in-run output at a stopped simulation clock', () => {
  for (const flag of ['after_episode_end', 'request_after_physical_end', 'response_after_physical_end']) {
    const late = {...response, [flag]: true};
    assert.equal(availableOutput(late, 2.662), false, flag);
    assert.equal(availableOutput(late, 100), false, flag);
  }
});

test('absent, malformed, or chronologically impossible replies are unavailable', () => {
  for (const call of [null, {...response, output_ref: null},
    {...response, request_sim_time_s: undefined}, {...response, response_sim_time_s: undefined},
    {...response, request_sim_time_s: '0.576'}, {...response, response_sim_time_s: '2.662'},
    {...response, response_sim_time_s: NaN}, {...response, response_sim_time_s: Infinity},
    {...response, request_sim_time_s: 4}]) {
    assert.equal(availableOutput(call, 10), false);
  }
  assert.equal(availableOutput(response, Infinity), false);
});

test('physical endpoint uses event order to exclude equal-time cleanup', () => {
  // These endpoint IDs/times mirror the retained baseline C01 episode.
  const endpoint = {event_id: 2879, sim_time_s: 199.1060000002226};
  const cleanup = {event_id: 2880, sim_time_s: endpoint.sim_time_s};
  const rows = [endpoint, cleanup];
  assert.equal(atOrBefore(rows, endpoint.sim_time_s), cleanup);
  const physical = rows.filter(row => withinPhysicalEnd(row, endpoint.event_id));
  assert.deepEqual(physical, [endpoint]);
  assert.equal(atOrBefore(physical, endpoint.sim_time_s), endpoint);
});

test('nested file writes need no invented after-end flag when their source event ID is known', () => {
  const writes = [{event_id: 20, candidate_event_index: 0, sim_time_s: 3},
    {event_id: 22, candidate_event_index: 0, sim_time_s: 3}];
  assert.deepEqual(writes.filter(row => withinPhysicalEnd(row, 21)), [writes[0]]);
});

test('request IDs can be selected explicitly and exact endpoint IDs remain allowed', () => {
  assert.equal(withinPhysicalEnd({request_event_id: 21}, 21, 'request_event_id'), true);
  assert.equal(withinPhysicalEnd({request_event_id: 22}, 21, 'request_event_id'), false);
  assert.equal(withinPhysicalEnd({response_event_id: 22}, 21, 'response_event_id'), false);
});

test('missing, string, and nonfinite event IDs fail closed', () => {
  for (const row of [null, {}, {event_id: '21'}, {event_id: NaN}, {event_id: Infinity}]) {
    assert.equal(withinPhysicalEnd(row, 21), false);
  }
  for (const end of [undefined, null, '21', NaN, Infinity]) {
    assert.equal(withinPhysicalEnd({event_id: 21}, end), false);
  }
});
