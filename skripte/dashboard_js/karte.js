// Weltkarte des Dashboards (wird von skripte/live_dashboard.py in die Seite eingebettet).
// Erwartet die globalen Konstanten KENNZAHLEN, LAENDER, PLAN, META, REGIONEN, RAMPE (stehen davor im HTML) sowie
// d3, topojson und WELT (data/live/vendor/, lokal; keine Abhängigkeit von Webdiensten außer den optionalen Landesteilen).
// Projektion: Equal Earth (Šavrič/Patterson/Jenny 2018; flächentreu, nicht eurozentrisch; von der Afrikanischen Union
// als Ersatz für Mercator empfohlen). Keine Mercator-Projektion. Die Antarktis wird nicht gezeichnet.
// Bedienung: Klick auf ein Land zoomt hinein (nochmal klicken zoomt heraus), Ziehen verschiebt, Strg + Mausrad zoomt, „Reset view“ setzt zurück.
(() => {
  const box = document.getElementById('karte'), sel = document.getElementById('kz'), ans = document.getElementById('ansicht'),
        geb = document.getElementById('gebiet'), leg = document.getElementById('kz-legende'), hinweis = document.getElementById('kz-hinweis'),
        reset = document.getElementById('zoom-reset');
  if (typeof d3 === 'undefined' || typeof topojson === 'undefined' || typeof WELT === 'undefined') {
    box.innerHTML = '<p class="leer">Map libraries missing (data/live/vendor/). Rebuild the dashboard: python3 skripte/live_dashboard.py</p>';
    return;
  }
  for (const k of Object.keys(KENNZAHLEN)) sel.add(new Option(k, k));
  try { sel.value = localStorage.getItem('kz') || ''; ans.value = localStorage.getItem('ansicht') || 'laender';
        geb.value = localStorage.getItem('gebiet') || 'welt'; } catch (e) {}
  if (!sel.value && sel.options.length) sel.value = sel.options[0].value;
  if (!geb.value) geb.value = 'welt';
  const alle = topojson.feature(WELT, WELT.objects.countries).features.filter(f => f.id !== '010');   // 010 = Antarktis
  const geplant = f => !!PLAN[f.id] || (f.properties.name === 'Kosovo' && PLAN.Kosovo);
  const geplantName = f => (PLAN[f.id] || PLAN.Kosovo || [])[0];
  const metaText = f => { const m = META[f.id] || (f.properties.name === 'Kosovo' ? META.Kosovo : null);
    return m ? '\n  ' + m[0] + ' · ' + m[1] + (m[2] ? ' · EU member' : '') : ''; };
  const W = 960, H = 500;
  // Welt ohne Antarktis: auf den Bereich 58° S bis 84° N einpassen
  const weltRahmen = {type: 'MultiPoint', coordinates: [[-180, 0], [180, 0], [-180, -57], [180, -57], [0, -57], [0, 84], [-170, 84], [170, 84]]};
  const projWelt = d3.geoEqualEarth().fitExtent([[4, 4], [W - 4, H - 4]], weltRahmen);
  const europaRahmen = {type: 'MultiPoint', coordinates: [[-24, 35], [44, 35], [44, 71], [-24, 71], [10, 36], [10, 70]]};
  const projEuropa = d3.geoEqualEarth().rotate([-12, 0]).fitExtent([[10, 10], [W - 10, H - 10]], europaRahmen);
  const svg = d3.select(box).html('').append('svg').attr('viewBox', `0 0 ${W} ${H}`)
    .attr('role', 'img').attr('aria-label', 'World map (Equal Earth projection)');
  const wurzel = svg.append('g');
  const laender = wurzel.append('g').selectAll('path').data(alle).join('path');
  const regionenG = wurzel.append('g');
  let regFl = regionenG.append('g').selectAll('path'), regPkt = regionenG.append('g').selectAll('circle'), nuts = null, zk = 1;
  const punkte = Object.entries(REGIONEN).filter(([k, r]) => r.punkt).map(([key, r]) => ({key, ...r}));
  regPkt = regPkt.data(punkte).join('circle').attr('class', 'land punktgruppe').attr('r', 5);
  function flaechenBauen() {
    const flaechen = [];
    for (const [key, r] of Object.entries(REGIONEN)) {
      let g = null;
      if (r.nuts && nuts) {
        const obj = nuts.objects[Object.keys(nuts.objects)[0]];
        g = topojson.merge(nuts, obj.geometries.filter(x => [].concat(r.nuts).some(p => x.properties.NUTS_ID.startsWith(p))));
      } else if (r.welt) {
        const f = alle.find(f => f.properties.name === r.welt); g = f && f.geometry;
      }
      if (g) flaechen.push({type: 'Feature', key, geometry: g});
    }
    regFl = regionenG.insert('g', ':first-child').selectAll('path').data(flaechen).join('path').attr('class', 'land region');
  }
  flaechenBauen();
  // Landesteile (NUTS) sind optional: höchstens 10 s warten, die Karte erscheint sofort
  fetch('https://gisco-services.ec.europa.eu/distribution/v2/nuts/topojson/NUTS_RG_20M_2016_4326_LEVL_3.json',
        {signal: AbortSignal.timeout(10000)}).then(r => r.json()).then(j => { nuts = j; regionenG.selectAll('*').remove();
          regFl = regionenG.append('g').selectAll('path'); regPkt = regionenG.append('g').selectAll('circle')
            .data(punkte).join('circle').attr('class', 'land punktgruppe').attr('r', 5 / zk); flaechenBauen(); pfade(); zeichnen(); }).catch(() => {});
  let proj = projWelt, pfad = d3.geoPath(proj);
  function pfade() {
    proj = geb.value === 'europa' ? projEuropa : projWelt; pfad = d3.geoPath(proj);
    laender.attr('d', pfad); regFl.attr('d', pfad);
    regPkt.attr('cx', d => proj(d.punkt)[0]).attr('cy', d => proj(d.punkt)[1]);
  }
  // Zoom: Ziehen verschiebt, Strg + Mausrad zoomt (das Mausrad allein scrollt weiter die Seite), Klick auf ein Land zoomt hinein
  const zoom = d3.zoom().scaleExtent([1, 14]).translateExtent([[0, 0], [W, H]])
    .filter(e => (!e.ctrlKey || e.type === 'wheel') && !e.button && (e.type !== 'wheel' || e.ctrlKey) && e.type !== 'dblclick')
    .on('zoom', e => { zk = e.transform.k; wurzel.attr('transform', e.transform); regPkt.attr('r', 5 / zk); });
  svg.call(zoom);
  function hauptteil(f) {   // bei Landesteilen in Übersee (Frankreich, USA, Russland …) den größten Teil nehmen
    if (f.geometry.type !== 'MultiPolygon') return f;
    let best = null, ba = -1;
    for (const p of f.geometry.coordinates) { const a = d3.geoArea({type: 'Polygon', coordinates: p}); if (a > ba) { ba = a; best = p; } }
    return {type: 'Feature', geometry: {type: 'Polygon', coordinates: best}};
  }
  function hinein(f) {
    const [[x0, y0], [x1, y1]] = pfad.bounds(hauptteil(f));
    const k = Math.min(14, 0.8 / Math.max((x1 - x0) / W, (y1 - y0) / H));
    svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  }
  function zuruecksetzen() { svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity); }
  reset.addEventListener('click', () => { aktuell = null; zuruecksetzen(); });
  let aktuell = null;   // zuletzt hineingezoomtes Land: nochmal darauf klicken zoomt wieder heraus
  laender.on('click', (e, f) => {
    if (e.defaultPrevented) return;
    if (aktuell === f.id && zk > 1.05) { aktuell = null; zuruecksetzen(); } else { aktuell = f.id; hinein(f); }
  });
  function zeichnen() {
    const k = KENNZAHLEN[sel.value]; if (!k) return;
    const regional = ans.value === 'regionen';
    try { localStorage.setItem('kz', sel.value); localStorage.setItem('ansicht', ans.value); localStorage.setItem('gebiet', geb.value); } catch (e) {}
    pfade();
    const landWerte = regional ? k.landesweit : k.werte;
    const werte = [...Object.values(landWerte), ...(regional ? Object.values(k.regionen) : [])].map(v => v[0]);
    const max = d3.max(werte) || 1;
    const farbe = d3.scaleQuantize().domain([0, max]).range(RAMPE);
    const fmt = v => k.einheit === '%' ? v.toFixed(1) + ' %' : Math.round(v).toLocaleString('en-GB');
    const txt = (name, w) => name + ': ' + (w ? fmt(w[0]) + ' (' + w[1] + ')' : 'too little data');
    const gw = key => REGIONEN[key] && REGIONEN[key].iso ? k.landesweit[REGIONEN[key].iso] : k.regionen[key];
    const gname = key => key.split('|')[1] + (REGIONEN[key] && REGIONEN[key].iso ? ' (UK-wide outlets)' : '');
    const gruppenText = (land, nurUebersee) => Object.keys(REGIONEN)
      .filter(r => r.startsWith(land + '|') && (!nurUebersee || REGIONEN[r].uebersee))
      .map(r => '\n  · ' + txt(gname(r), gw(r))).join('');
    laender.attr('class', f => LAENDER[f.id] ? 'land' + (landWerte[f.id] ? '' : ' ohne') : (geplant(f) ? 'geplant' : 'rest'))
      .attr('fill', f => LAENDER[f.id] && landWerte[f.id] ? farbe(landWerte[f.id][0]) : null)
      .attr('data-tip', f => LAENDER[f.id]
        ? txt(LAENDER[f.id] + (regional ? ' (nationwide outlets)' : ''), landWerte[f.id]) + metaText(f) + gruppenText(LAENDER[f.id], regional)
        : geplant(f) ? geplantName(f) + ': planned – no outlets configured yet, counted as 0' + metaText(f)
                     : f.properties.name + ': not in the sample');
    regFl.style('display', regional ? null : 'none')
      .attr('fill', d => gw(d.key) ? farbe(gw(d.key)[0]) : null)
      .attr('class', d => 'land region' + (gw(d.key) ? '' : ' ohne'))
      .attr('data-tip', d => txt(d.key.split('|')[0] + ' · ' + gname(d.key), gw(d.key)));
    regPkt.style('display', regional ? null : 'none')
      .attr('fill', d => k.regionen[d.key] ? farbe(k.regionen[d.key][0]) : null)
      .attr('class', d => 'land punktgruppe' + (k.regionen[d.key] ? '' : ' ohne'))
      .attr('data-tip', d => txt(d.key.replace('|', ' · ') + ' (dot: ' + d.ort + ')', k.regionen[d.key]));
    leg.innerHTML = fmt(0) + ' ' + RAMPE.map(c => `<i style="background:${c}"></i>`).join('') + ' ' + fmt(max) +
      ' <i style="background:var(--achse);margin-left:10px"></i> too little data' +
      ' <i class="geplant-leg" style="margin-left:10px"></i> planned, not collected yet';
    hinweis.textContent = (regional
      ? 'Countries show only the nationwide outlets; regions as areas (outlined), language groups without a territory of their own as a dot roughly where the group forms a local majority or is most concentrated. '
      : 'All outlets of a country together, including regional and minority media. Hovering over a country shows its continent, UN region and regions/language groups. ')
      + 'Click a country to zoom in (click it again to zoom out), drag to pan, Ctrl + mouse wheel to zoom. Projection: Equal Earth (equal-area, not Mercator); Antarctica is not drawn. '
      + 'Countries in the orange tint are planned for the sample (former colonies, Western Balkans, USA, Russia) and still count as 0.';
  }
  window.karteNeuZeichnen = zeichnen;   // das Live-Panel (live.js) schreibt neue Zahlen in KENNZAHLEN und ruft das hier auf
  sel.addEventListener('change', zeichnen); ans.addEventListener('change', zeichnen);
  geb.addEventListener('change', () => { svg.call(zoom.transform, d3.zoomIdentity); zeichnen(); });
  zeichnen();
  laender.on('mouseenter', (e, f) => {
    if (ans.value === 'regionen' || !LAENDER[f.id]) return;
    const praefix = LAENDER[f.id] + '|';
    regFl.style('display', d => d.key.startsWith(praefix) ? null : 'none').style('pointer-events', 'none');
    regPkt.style('display', d => d.key.startsWith(praefix) ? null : 'none').style('pointer-events', 'none');
  }).on('mouseleave', () => {
    if (ans.value === 'regionen') return;
    regFl.style('display', 'none'); regPkt.style('display', 'none');
  });
  ans.addEventListener('change', () => { regFl.style('pointer-events', null); regPkt.style('pointer-events', null); });
})();
