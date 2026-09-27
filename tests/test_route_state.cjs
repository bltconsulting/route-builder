const assert = require('node:assert/strict');
const test = require('node:test');
const RouteState = require('../templates/route_state.js');

const stops = [
  {lat: 42.0, lon: -83.0}, {lat: 42.1, lon: -83.0}, {lat: 42.2, lon: -83.0}
];

test('nearest entry rotates the canonical loop', () => {
  const entry = RouteState.nearest(stops, 42.2, -83.0);
  assert.deepEqual(RouteState.start(stops, entry, 'waze').order, [2, 0, 1]);
});

test('navigation destination changes with the current stop', () => {
  let state = RouteState.start(stops, 0, 'waze');
  const first = RouteState.navigationUrl(stops[RouteState.current(state)], 'waze');
  state = RouteState.change(state, 'done');
  const second = RouteState.navigationUrl(stops[RouteState.current(state)], 'waze');
  assert.notEqual(first, second);
  assert.match(second, /^https:\/\/waze\.com\/ul\?ll=42\.1%2C-83&navigate=yes$/);
});

test('done, skip, undo, revisit, finish preserve progress', () => {
  let state = RouteState.start(stops, 1, 'google');
  state = RouteState.change(state, 'done');
  state = RouteState.change(state, 'skip');
  assert.equal(RouteState.current(state), 0);
  assert.deepEqual(state.skipped, [2]);
  state = RouteState.change(state, 'undo');
  assert.equal(RouteState.current(state), 2);
  assert.deepEqual(state.skipped, []);
  state = RouteState.change(state, 'skip');
  state = RouteState.change(state, 'done');
  assert.equal(state.phase, 'choice');
  state = RouteState.change(state, 'revisit');
  assert.equal(RouteState.current(state), 2);
  state = RouteState.change(state, 'done');
  assert.deepEqual(state.skipped, []);
  assert.equal(state.phase, 'choice');
  state = RouteState.change(state, 'finish');
  assert.equal(state.phase, 'finished');
  state = RouteState.change(state, 'undo');
  assert.equal(state.phase, 'choice');
  assert.deepEqual(JSON.parse(JSON.stringify(state)).done, [1, 0, 2]);
});
