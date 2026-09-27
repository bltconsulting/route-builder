/* Pure route transitions are kept here so the generated file and tests use the same logic. */
const RouteState = (() => {
  const apps = ['waze', 'google', 'apple'];
  function nearest(stops, lat, lon) {
    const rad = Math.PI / 180;
    const score = s => {
      const dLat = (s.lat - lat) * rad, dLon = (s.lon - lon) * rad;
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat * rad) * Math.cos(s.lat * rad) * Math.sin(dLon / 2) ** 2;
      return a;
    };
    return stops.reduce((best, s, i) => score(s) < score(stops[best]) ? i : best, 0);
  }
  function start(stops, entry, app) {
    const order = stops.map((_, i) => (i + entry) % stops.length);
    return {phase: 'primary', order, position: 0, done: [], skipped: [], revisit: [], app, history: []};
  }
  function snapshot(state) {
    const {phase, position, done, skipped, revisit} = state;
    return {phase, position, done: [...done], skipped: [...skipped], revisit: [...revisit]};
  }
  function change(state, action) {
    if (action === 'undo') {
      if (!state.history.length) return state;
      const history = [...state.history], previous = history.pop();
      return {...state, ...previous, history};
    }
    const next = {...state, done: [...state.done], skipped: [...state.skipped], revisit: [...state.revisit], history: [...state.history, snapshot(state)]};
    if (action === 'done' || action === 'skip') {
      if (!['primary', 'revisit'].includes(state.phase)) return state;
      const index = state.phase === 'primary' ? state.order[state.position] : state.revisit[state.position];
      if (index === undefined) return state;
      if (action === 'done') {
        next.done.push(index);
        if (state.phase === 'revisit') next.skipped = next.skipped.filter(i => i !== index);
      } else if (!next.skipped.includes(index)) next.skipped.push(index);
      next.position++;
      if (state.phase === 'primary' && next.position === state.order.length) next.phase = 'choice';
      if (state.phase === 'revisit' && next.position === state.revisit.length) next.phase = 'choice';
      return next;
    }
    if (action === 'revisit' && state.phase === 'choice' && state.skipped.length) {
      next.revisit = state.order.filter(i => state.skipped.includes(i));
      next.position = 0;
      next.phase = 'revisit';
      return next;
    }
    if (action === 'finish' && state.phase === 'choice') {
      next.phase = 'finished';
      return next;
    }
    return state;
  }
  function current(state) {
    return state.phase === 'primary' ? state.order[state.position] :
      state.phase === 'revisit' ? state.revisit[state.position] : undefined;
  }
  function navigationUrl(stop, app) {
    const destination = encodeURIComponent(`${stop.lat},${stop.lon}`);
    if (app === 'waze') return `https://waze.com/ul?ll=${destination}&navigate=yes`;
    if (app === 'google') return `https://www.google.com/maps/dir/?api=1&destination=${destination}&travelmode=driving&dir_action=navigate`;
    if (app === 'apple') return `https://maps.apple.com/?daddr=${destination}&dirflg=d`;
    throw new Error('Unknown navigation app');
  }
  return {apps, nearest, start, change, current, navigationUrl};
})();
if (typeof module !== 'undefined') module.exports = RouteState;
