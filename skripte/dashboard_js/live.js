// Echtzeit-Panel des Dashboards (von skripte/live_dashboard.py eingebettet). Fragt alle 5 s /live.json beim Live-Server ab
// (skripte/live_server.py, http://127.0.0.1:8765/dashboard.html). Beim Öffnen als Datei (file://) gibt es keinen Server:
// dann zeigt das Panel den Stand vom letzten Bau (LIVE0) und die Seite lädt sich alle 2 Minuten neu, wenn sie oben steht.
// Erwartet die globalen Konstanten LIVE0 (Stand beim Bau) und BAU_ZEIT (Kennung dieses Baus; steht auch in data/live/dashboard.version).
(() => {
  const box = document.getElementById('live-inhalt'), punkt = document.getElementById('live-punkt'), banner = document.getElementById('neu-banner');
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
  const zahl = n => (n == null || isNaN(n) ? '–' : Number(n).toLocaleString('en-GB'));
  const chip = (txt, zustand) => `<span class="chip-s ${zustand}">${esc(txt)}</span>`;
  const vor = s => s < 90 ? s + ' s ago' : Math.round(s / 60) + ' min ago';
  let start = null;
  function spark(werte, titel) {
    const v = werte.filter(x => x != null);
    if (v.length < 2) return `<span class="klein">${esc(titel)}: collecting …</span>`;
    const mx = Math.max(...v, 1), mn = Math.min(...v, 0), W = 180, H = 36;
    const d = v.map((y, i) => `${i ? 'L' : 'M'}${(i / (v.length - 1) * W).toFixed(1)},${(H - 3 - (H - 8) * (y - mn) / ((mx - mn) || 1)).toFixed(1)}`).join(' ');
    return `<div class="spark"><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img"><path d="${d}" class="linie"/></svg>` +
           `<span class="klein">${esc(titel)} · now ${zahl(v[v.length - 1])}</span></div>`;
  }
  // ---- Abschnitte unter dem Live-Panel: Weltkarte, Retrieval by country, Pace (nur neu zeichnen, wenn sich etwas geändert hat) ----
  const letzte = {};
  const aenderung = (name, sig) => { if (letzte[name] === sig) return false; letzte[name] = sig; return true; };
  const mon = t => new Date(t * 1000).toLocaleString('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
  function balkenSvg(daten, lw, bw) {   // wie hbars() in skripte/live_dashboard.py: [Beschriftung, Prozent, Tooltip]
    if (!daten.length) return '<p class="leer">no data yet</p>';
    const h = 22;
    return `<svg viewBox="0 0 ${lw + bw + 90} ${daten.length * h + 4}" class="chart" role="img">` + daten.map(([lab, v, tip], k) => {
      const y = k * h + 2, w = Math.max(bw * v / 100, v === 0 ? 0 : 2);
      return `<rect x="${lw}" y="${y + 4}" width="${bw}" height="${h - 8}" rx="4" class="spur"/><g data-tip="${esc(tip)}"><rect x="${lw}" y="${y}" width="${lw + bw + 90}" height="${h}" class="hit"/>` +
        `<text x="${lw - 8}" y="${y + 15}" text-anchor="end" class="lab">${esc(lab)}</text><rect x="${lw}" y="${y + 4}" width="${w.toFixed(1)}" height="${h - 8}" rx="4" class="bar"/>` +
        `<text x="${(lw + w + 6).toFixed(1)}" y="${y + 15}" class="val">${v.toFixed(1)} %</text></g>`;
    }).join('') + '</svg>';
  }
  function liniensvg(pts, label) {   // wie linie(): [[Unixzeit, Wert], …]
    if (pts.length < 2) return '<p class="leer">the time series starts with the second run</p>';
    const t0 = pts[0][0], t1 = pts[pts.length - 1][0], span = (t1 - t0) || 1, mx = Math.max(...pts.map(p => p[1]), 1), W = 560, H = 140;
    const xy = pts.map(([t, v]) => [30 + W * (t - t0) / span, H - (H - 14) * v / mx]);
    const dpath = xy.map(([x, y], k) => `${k ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    const punkte = pts.map(([t, v], k) => `<g data-tip="${esc(mon(t) + ': ' + zahl(v))}"><rect x="${(xy[k][0] - 6).toFixed(1)}" y="0" width="12" height="${H}" class="hit"/><circle cx="${xy[k][0].toFixed(1)}" cy="${xy[k][1].toFixed(1)}" r="4" class="punkt"/></g>`).join('');
    return `<svg viewBox="0 0 ${W + 60} ${H + 22}" class="chart" role="img" aria-label="${esc(label)}"><line x1="30" y1="${H}" x2="${W + 30}" y2="${H}" class="achse"/><path d="${dpath}" class="linie"/>${punkte}` +
      `<text x="30" y="${H + 16}" class="klein">${esc(mon(t0))}</text><text x="${W + 30}" y="${H + 16}" text-anchor="end" class="klein">${esc(mon(t1))}</text>` +
      `<text x="${xy[xy.length - 1][0].toFixed(1)}" y="${(xy[xy.length - 1][1] - 10).toFixed(1)}" text-anchor="end" class="val">${zahl(pts[pts.length - 1][1])}</text></svg>`;
  }
  function abschnitteAktualisieren(d) {
    const ab = d.abdeckung || {}, land = ab.land || {};
    if (!ab.summe) return;
    const en = l => (ab.iso && LAENDER[ab.iso[l]]) || l;   // Länderlisten kommen deutsch; die Seite zeigt englische Namen (LAENDER: ISO-Nummer -> englischer Name)
    // Retrieval by country
    const ziel = document.getElementById('abruf-inhalt');
    if (ziel && aenderung('abruf', ab.stand)) {
      const namen = [...new Set([...Object.keys(land), ...(ab.konfiguriert || [])])].filter(l => l !== '?');
      namen.sort((a, b) => ((land[b] || [0])[0] - (land[a] || [0])[0]) || a.localeCompare(b));
      const daten = namen.map(l => { const [r, t, art, m] = land[l] || [0, 0, 0, 0];
        return [en(l), r ? 100 * t / r : 0, r ? `${en(l)}: ${zahl(t)} of ${zahl(r)} relevant URLs with a text of at least 300 characters (${zahl(m)} stored as articles, ${zahl(art)} articles in total)` : `${en(l)}: no URL list yet – URL collection pending, counted as 0`]; })
        .concat((ab.geplant || []).map(l => [en(l) + ' (planned)', 0, en(l) + ': planned – no outlets configured yet, counted as 0']));
      ziel.innerHTML = balkenSvg(daten, 215, 380);
    }
    // Pace: Zeitreihe des letzten Baus plus der Live-Punkt von jetzt
    const g = document.getElementById('pace-geholt'), u = document.getElementById('pace-ue');
    const vp = d.abdeckung_verlauf || [], ueNow = ((d.db || {}).uebersetzt || {}).nllb_halbseite;
    if (g && u && vp.length && aenderung('pace', ab.stand + ':' + ueNow)) {
      g.innerHTML = liniensvg(vp.map(p => [p[0], p[1]]).concat([[d.zeit_unix, ab.summe.matched]]), 'URLs with a stored article (cumulative)');
      u.innerHTML = liniensvg(vp.map(p => [p[0], p[2]]).concat(ueNow != null ? [[d.zeit_unix, ueNow]] : []), 'Half pages translated');
    }
    // Weltkarte: die beiden Kennzahlen, die aus dem Scraper kommen (Ländersicht); die Frames bleiben vom letzten Bau
    if (typeof KENNZAHLEN !== 'undefined' && window.karteNeuZeichnen && aenderung('karte', ab.stand)) {
      const k1 = KENNZAHLEN['Retrieval: share of relevant URLs with text'], k2 = KENNZAHLEN['Articles parsed'];
      for (const [name, iso] of Object.entries(ab.iso || {})) {
        if (!(iso in LAENDER)) continue;
        const [r, t, art] = land[name] || [0, 0, 0, 0];
        if (k1) { if (r) k1.werte[iso] = [100 * t / r, `${zahl(t)} of ${zahl(r)} URLs`]; else if ((ab.konfiguriert || []).includes(name)) k1.werte[iso] = [0, 'no URL list yet, counted as 0']; else delete k1.werte[iso]; }
        if (k2) { if (art) k2.werte[iso] = [art, `${zahl(art)} articles`]; else delete k2.werte[iso]; }
      }
      window.karteNeuZeichnen();
    }
  }
  function render(d, live) {
    if (!d || !d.dienste) { box.innerHTML = '<p class="leer">No data.</p>'; return; }
    const s = d.dienste, a = d.abruf || {}, db = d.db || {}, st = d.status || {}, pl = d.platte || {};
    if (!start && db.artikel != null) start = {artikel: db.artikel, ue: (db.uebersetzt || {}).nllb_halbseite, csv: (d.status || {}).artikel_summe, t: d.zeit_unix};
    const ue = (db.uebersetzt || {});
    const tempo = a.seiten_5min != null ? a.seiten_5min / 5 : null;
    const ab = d.abdeckung || {}, as = ab.summe || {};
    const mc = d.mediacloud || {}, sl = d.scraper_log || {}, ul = d.uebersetzer_log || {}, v0 = d.verlauf || [];
    const alter = z => z ? Math.max(0, d.zeit_unix - new Date(String(z).replace(' ', 'T')).getTime() / 1000) : null;
    const logTab = zl => (zl || []).length ? `<details><summary>Latest log lines</summary><table>${zl.map(x => `<tr><td>${esc(x.zeit)}</td><td>${esc(x.text)}</td></tr>`).join('')}</table></details>` : '';
    const stufe = (name, zustand, marke, inhalt) => `<div class="stufe"><div class="stufe-kopf"><b>${esc(name)}</b> ${chip(marke, zustand)}</div><div class="stufe-text">${inhalt}</div></div>`;
    // Übersetzungstempo aus dem Verlauf (Zählerstand der übersetzten Halbseiten über die letzten Messpunkte)
    const vu = v0.filter(x => x.uebersetzt != null);
    let uebTempo = null;
    if (vu.length > 2) { const dt = (vu[vu.length - 1].t - vu[0].t) / 3600; if (dt > 0.08) uebTempo = (vu[vu.length - 1].uebersetzt - vu[0].uebersetzt) / dt; }
    const offenUe = db.offen_halbseite;
    // 1. Scraper
    let scrInhalt = '', scrMarke = 'stopped', scrZust = 'warn';
    const phase1 = !!(mc.zuletzt && mc.zuletzt.vor_s < 900 && (mc.offen || 0) > 0);
    if (s.scraper.aktiv) {
      const gr = mc.gruppen || {};
      scrMarke = 'running'; scrZust = 'an';
      let phase;
      if (phase1) phase = '<b>Phase 1 of 2: collecting URL lists via Media Cloud</b> for the new outlets (Balkans, post-colonial states, USA, Russia, India, Pakistan …). No article texts are downloaded in this phase, so nothing new reaches the database or translation yet. Media Cloud allows about 10 requests per minute.';
      else if (((d.scraper_aktiv || {}).arbeitet || []).some(x => x.phase === 'urls')) phase = '<b>Phase 1 of 2: collecting URL lists per outlet</b> (robots.txt, sitemaps) for the outlets that have none yet. Large sitemaps can take many minutes per outlet; no article texts are downloaded in this phase.';
      else if ((a.seiten_15min || 0) > 0 || (a.csv || {}).n_15min) phase = '<b>Phase 2 of 2: downloading and parsing article texts</b>';
      else phase = '<b>Running, but no visible activity in the last 15 minutes</b> – check the log lines below.';
      const balken = phase1 ? Object.keys(gr).map(g => `<div class="klein">Source group ${esc(g)}: ${gr[g]} of ${mc.fenster_gesamt} time windows</div><progress max="${mc.fenster_gesamt}" value="${gr[g]}" style="width:100%"></progress>`).join('') : '';
      const eta = phase1 && mc.eta_min != null ? `<p class="klein">Roughly ${mc.eta_min < 90 ? mc.eta_min + ' min' : (mc.eta_min / 60).toFixed(1) + ' h'} left for this phase (based on the last 45 min; big months take longer than single days). Last window finished ${vor(mc.zuletzt.vor_s)}: ${esc(mc.zuletzt.von)} to ${esc(mc.zuletzt.bis)}, group ${mc.zuletzt.gruppe}.</p>` : '';
      const lim = phase1 && sl.pausen > 5 ? '<p class="klein">Media Cloud is throttling requests right now; the scraper waits (30–60 s) and retries automatically. That is normal at this request rate.</p>' : '';
      const sa = d.scraper_aktiv || {}, ar = sa.arbeitet || [], phasenName = {urls: 'collecting URLs', texte: 'downloading texts'};
      const dauer = sek => sek < 90 ? sek + ' s' : Math.round(sek / 60) + ' min';
      const arbeit = !sa.log_da ? '<p class="klein">Per-outlet activity is shown after the next scraper start.</p>' :
        (ar.length ? `<p class="klein">Working on ${ar.length} outlet(s) right now (done since the scraper started: ${sa.fertig.urls || 0} URL lists, ${sa.fertig.texte || 0} text runs). Outlets running for more than 20 minutes are marked.</p><table><tr><th>Outlet</th><th>Doing</th><th>Running for</th></tr>` +
          ar.map(x => `<tr><td>${esc(x.medium)}</td><td>${esc(phasenName[x.phase] || x.phase)}</td><td>${dauer(x.seit_s)}${x.seit_s > 1200 ? ' ⚠ long' : ''}</td></tr>`).join('') + '</table>'
          : '<p class="klein">No outlet is being worked on at the moment.</p>');
      scrInhalt = `<p>${phase}</p>${balken}${eta}${arbeit}${lim}${logTab(sl.zeilen)}`;
    } else scrInhalt = '<p>The scraper is not running. Start it with: <code>systemctl --user start masterarbeit-scraper</code></p>';
    // 2. Import (läuft im Übersetzungsdienst)
    const impZeilen = (ul.zeilen || []).filter(x => /neue Artikel importiert/.test(x.text)), impLetzte = impZeilen[impZeilen.length - 1];
    const impN = impLetzte ? (impLetzte.text.match(/(\d+) neue Artikel/) || [])[1] : null;
    const impAktiv = s.uebersetzung.aktiv || s.import.aktiv;
    const impInhalt = '<p>Every 2 minutes, new scraper result files are imported into the database (inside the translation service).' +
      (impLetzte ? ` Last check ${esc(impLetzte.zeit)}: <b>${esc(impN)}</b> new article(s).` : '') +
      (ul.zustand ? ` <b>Right now:</b> ${ul.zustand.phase === 'import' ? 'importing new scraper files' : ul.zustand.phase === 'uebersetzen' ? 'translating; the next import in about ' + Math.max(0, Math.round((ul.zustand.paket_ende - d.zeit_unix) / 60)) + ' min' : 'waiting 2 min (nothing left to translate)'} (state ${vor(Math.round(d.zeit_unix - ul.zustand.zeit))}).` : '') +
      (ul.import_wartend != null ? ` <b>${zahl(ul.import_wartend)}</b> scraper file(s) written since then are waiting for the next check (it runs between translation batches, about every 8 minutes).` : '') +
      (db.letzter_import ? ` The most recent article in the database was imported ${vor(alter(db.letzter_import))}.` : '') +
      (s.scraper.aktiv && phase1 ? ' Nothing new is expected until the scraper has finished collecting URLs (phase 1).' : '') + '</p>';
    // 3. Übersetzung
    let ueInhalt;
    if (!s.uebersetzung.aktiv) ueInhalt = '<p>The translation service is not running. Start it with: <code>systemctl --user start masterarbeit-uebersetzer</code></p>';
    else if (offenUe > 0) ueInhalt = `<p><b>Translating on the GPU:</b> ${zahl(offenUe)} half pages still open${uebTempo > 1 ? `, about ${zahl(Math.round(uebTempo))} per hour (done approx. ${new Date((d.zeit_unix + offenUe / uebTempo * 3600) * 1000).toLocaleString('en-GB', {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'})})` : ''}.</p>`;
    else ueInhalt = `<p><b>Idle: nothing left to translate.</b> All relevant non-English articles in the database are translated (last translation ${db.letzte_uebersetzung ? vor(alter(db.letzte_uebersetzung)) : '–'}). It continues automatically as soon as new articles are imported.</p>`;
    if (ul.relevant) ueInhalt += `<p class="klein">${esc(ul.relevant)}</p>`;
    ueInhalt += logTab(ul.zeilen);
    // 4. Dashboard, 5. Statistik
    const bauInhalt = `<p>This page is rebuilt every 5 minutes (about 3 minutes of work). Last build: ${d.dashboard_stand ? new Date(d.dashboard_stand * 1000).toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'}) + ' (' + vor(Math.round(d.zeit_unix - d.dashboard_stand)) + ')' : '–'}. The tiles and this panel update every 5 seconds on their own.</p>`;
    const methInhalt = s.methoden.aktiv ? '<p>The statistical analyses are running now.</p>' : '<p>Deferred to the very end of the data collection (to keep the PC free).</p>';
    // 6. Nexis-Export (nur wenn es ihn gibt oder er läuft)
    const nx = d.nexis || {};
    let nexisStufe = '';
    if (nx.laeufe || nx.artikel) {
      // Fortschritt = fertige Fenster von allen Fenstern (Medium x Zeitraum), ohne Schätzung der Artikelzahl
      const pr = nx.fenster_gesamt ? 100 * nx.fenster_fertig / nx.fenster_gesamt : null;
      const rest = null;
      const herz = (nx.herz || []).map(h => `<tr><td>${esc(h.profil.replace('nexis-', 'session '))}</td><td>${esc(h.text)}</td><td>${h.alter_s > 600 ? '⚠ ' : ''}${vor(h.alter_s)}</td></tr>`).join('');
      const medien = (nx.je_medium || []).map(m => `<tr><td>${esc(m.medium)}</td><td>${zahl(m.artikel)}</td><td>${m.fenster_fertig} of 6 windows done</td><td>${zahl(m.treffer_bekannt)} hits in ${m.fenster_bekannt} known window(s)</td></tr>`).join('');
      nexisStufe = stufe('6 · Nexis Uni export (Uni VPN)', nx.laeufe ? 'an' : 'warn', nx.laeufe ? nx.laeufe + ' run(s) active' : 'not running',
        `<p><b>${zahl(nx.artikel)}</b> articles downloaded in ${zahl(nx.dateien)} files (RTF, 100 per file) · ${nx.fenster_fertig} of ${nx.fenster_gesamt} outlet-windows complete` +
        `${nx.rate_h ? ` · about ${zahl(nx.rate_h)} articles/hour` : ''}${rest != null ? ` · roughly ${rest < 1 ? Math.round(rest * 60) + ' min' : rest.toFixed(1) + ' h'} left (estimate)` : ''}.</p>` +
        (pr != null ? `<progress max="100" value="${pr.toFixed(1)}" style="width:100%"></progress><p class="klein">${pr.toFixed(0)} %: ${nx.fenster_fertig} of ${nx.fenster_gesamt} outlet-windows complete (a window is one outlet in one of the six study periods; sizes differ). Not in Nexis Uni: Aftenposten, VG.</p>` : '') +
        (herz ? `<table><tr><th>Run</th><th>Doing</th><th>Updated</th></tr>${herz}</table>` : '<p class="klein">No run reporting right now.</p>') +
        (medien ? `<details><summary>Per outlet</summary><table><tr><th>Outlet</th><th>Articles</th><th>Windows</th><th>Hits known</th></tr>${medien}</table></details>` : '') +
        `<p class="klein">Requests are paced (a download every 20–40 s per run, a run stops on any captcha, block or limit notice). The Uni VPN is ${nx.vpn ? 'active' : 'off'}; the scraper stays stopped while it is on, because the VPN routes all traffic and its requests would leave with the university address.</p>`);
    }
    const ql = d.qualitaet || {};
    const qualStufe = (ql.aktiv || ql.bewertet) ? stufe('7 · Translation quality scoring', ql.aktiv ? 'an' : 'aus', ql.aktiv ? 'running' : 'stopped',
      `<p>Rating half-page translations: <b>${zahl(ql.bewertet)}</b> of about ${zahl(ql.gesamt)} done (${(100 * ql.bewertet / ql.gesamt).toFixed(0)} %).</p>` +
      `<progress max="100" value="${(100 * ql.bewertet / ql.gesamt).toFixed(1)}" style="width:100%"></progress>` +
      '<p class="klein">The result (flagged share by language) appears in the section "Translation quality classifier" below after the next page build.</p>') : '';
    const tun = '<div class="live-tun"><h3>What is happening right now</h3>' +
      stufe('1 · Scraper', scrZust, scrMarke, scrInhalt) +
      stufe('2 · Import into the database', impAktiv ? 'an' : 'warn', impAktiv ? 'running' : 'stopped', impInhalt) +
      stufe('3 · Translation (NLLB)', !s.uebersetzung.aktiv ? 'warn' : (offenUe > 0 ? 'an' : 'aus'), !s.uebersetzung.aktiv ? 'stopped' : (offenUe > 0 ? 'translating' : 'idle'), ueInhalt) +
      stufe('4 · Dashboard build', s.dashboard_bau.aktiv ? 'an' : 'aus', s.dashboard_bau.aktiv ? 'rebuilding' : 'up to date', bauInhalt) +
      stufe('5 · Statistical analyses', s.methoden.aktiv ? 'warn' : 'aus', s.methoden.aktiv ? 'running' : 'deferred', methInhalt) + nexisStufe + qualStufe + '</div>';
    const warn = [];
    if (nx.vpn && s.scraper.aktiv) warn.push('The Uni VPN is active while the scraper is running: the scraper\'s requests leave with the university address. Stop one of them.');
    if (!s.scraper.aktiv) warn.push(nx.vpn ? 'The scraper is stopped on purpose while the Uni VPN is active (the VPN routes all traffic, so its requests would leave with the university address). After the Nexis export: Uni VPN off, then <code>systemctl --user start masterarbeit-scraper</code>.' : 'The scraper is not running. Start it with: <code>systemctl --user start masterarbeit-scraper</code>');
    if (pl.frei_gb != null && pl.frei_gb < 3) warn.push(`Disk almost full: ${pl.frei_gb} GB free – the scraper stops below 2.5 GB.`);
    const aktiv = (a.aktiv || []).length ? '<table><tr><th>Outlet</th><th>Country</th><th>Pages 5 min</th><th>Pages 15 min</th><th>Last page</th></tr>' +
      a.aktiv.map(x => `<tr><td>${esc(x.medium)}</td><td>${esc(x.land)}</td><td>${zahl(x.seiten_5min)}</td><td>${zahl(x.seiten_15min)}</td><td>${vor(x.vor_s)}</td></tr>`).join('') + '</table>'
      : ((a.csv || {}).n_15min ? '<p>The scraper stores full texts as CSV files: <b>' + a.csv.n_5min + '</b> outlet file(s) updated in the last 5 min, <b>' + a.csv.n_15min + '</b> in 15 min.</p><table><tr><th>Outlet</th><th>File size</th><th>Last write</th></tr>' + a.csv.neueste.map(x => `<tr><td>${esc(x.medium)}</td><td>${zahl(x.kb)} KB</td><td>${vor(x.vor_s)}</td></tr>`).join('') + '</table>'
      : `<p class="leer">No page downloaded and no outlet file written in the last 15 minutes${s.scraper.aktiv ? ' – the scraper is collecting URLs, waiting for a pause (robots.txt crawl delay) or has finished all outlets with a URL list.' : '.'}</p>`);
    const schr = (st.schreibend || []).length ? '<h3>Processing right now (article files written in the last 10 min)</h3><table><tr><th>Outlet</th><th>Last write</th><th>File size</th></tr>' +
      st.schreibend.map(x => `<tr><td>${esc(x.medium)}</td><td>${vor(x.vor_s)}</td><td>${x.mb} MB</td></tr>`).join('') + '</table><p class="klein">Includes parsing of pages that were downloaded earlier; these do not count as new downloads.</p>' : '';
    const ohne = st.n_ohne_url_liste ? `<p><b>${st.n_ohne_url_liste}</b> configured outlet(s) still without URL list: ${esc((st.ohne_url_liste || []).join(', '))} – the scraper collects their URLs first (sitemaps, Media Cloud).</p>` : '<p>All configured outlets have a URL list.</p>';
    const neu = (st.neueste_status || []).map(x => `<tr><td>${esc(x.medium)}</td><td>${esc(x.land)}</td><td>${esc(x.stand)}</td><td>${zahl(x.relevant)}</td><td class="fehler">${esc(x.fehler)}</td></tr>`).join('');
    const log = (db.log || []).map(x => `<tr><td>${esc(String(x.zeit).slice(5, 16))}</td><td>${esc(x.schritt)}</td><td>${x.n == null ? '' : esc(x.n)}</td><td>${esc(x.meldung)}</td></tr>`).join('');
    const arts = (db.neueste || []).map(x => `<tr><td>${esc(String(x.zeit).slice(5, 16))}</td><td>${esc(x.medium)}</td><td>${esc(x.titel)}</td></tr>`).join('');
    const v = d.verlauf || [];
    const kachelnHtml = `
      <div class="kacheln" style="margin: 12px 0 20px 0;">
        <div class="kachel"><div class="wert">${zahl(as.relevant)}</div><div class="klabel">relevant URLs</div><div class="sub">${st.n_listen || 0} outlets with a URL list</div></div>
        <div class="kachel"><div class="wert">${as.relevant ? (100 * (as.text_urls || 0) / as.relevant).toFixed(1) : '0.0'} %</div><div class="klabel">retrieved with text</div><div class="sub">${zahl(as.text_urls)} of ${zahl(as.relevant)} relevant URLs</div></div>
        <div class="kachel"><div class="wert">${zahl(tempo != null ? Math.round(tempo * 60) : null)}</div><div class="klabel">pages per hour</div><div class="sub">${tempo ? 'scraping pace, last 5 min' : 'no page downloads right now'}</div></div>
        <div class="kachel"><div class="wert">${zahl(as.article_text_ok)}</div><div class="klabel">articles with text</div><div class="sub">${zahl(as.articles)} parsed, ${zahl(as.paywall)} paywalled</div></div>
        <div class="kachel"><div class="wert">${zahl(db.artikel)}</div><div class="klabel">in the database</div><div class="sub">${zahl(db.relevant)} relevant</div></div>
        <div class="kachel"><div class="wert">${zahl(db.korpus)}</div><div class="klabel">in the analysis corpus</div><div class="sub">relevant + English or translated</div></div>
        <div class="kachel"><div class="wert">${zahl(ue.nllb_halbseite)}</div><div class="klabel">translated (NLLB)</div><div class="sub">half pages, ${zahl(db.offen_halbseite)} still open</div></div>
        <div class="kachel"><div class="wert">${uebTempo > 1 ? zahl(Math.round(uebTempo)) : '–'}</div><div class="klabel">translations per hour</div><div class="sub">${uebTempo > 1 ? 'half pages, last ' + Math.round((vu[vu.length - 1].t - vu[0].t) / 60) + ' min' : 'idle (nothing open)'}</div></div>
        <div class="kachel"><div class="wert">${pl.frei_gb != null ? pl.frei_gb + ' GB' : '–'}</div><div class="klabel">free disk</div><div class="sub">${pl.belegt_prozent != null ? pl.belegt_prozent + ' % used' : ''}</div></div>
      </div>
    `;
    box.innerHTML = (warn.length ? `<p class="warnbox">${warn.join('<br>')}</p>` : '') +
      `${kachelnHtml}${tun}` +
      `<div class="live-raster"><div><h3>Downloading right now</h3>${aktiv}${schr}${ohne}</div>` +
      `<div><h3>Trend (last ${Math.max(1, Math.round(v.length / 2))} min)</h3>${spark(v.map(x => x.seiten_pro_min), 'pages downloaded/min')}${spark(v.map(x => x.artikel_csv), 'articles stored (CSV)')}${spark(v.map(x => x.artikel), 'articles in DB')}${spark(v.map(x => x.uebersetzt), 'half pages translated')}` +
      `<h3>Latest imported articles</h3><table>${arts}</table></div></div>` +
      `<details><summary>Latest URL-collection / retrieval status per outlet</summary><table><tr><th>Outlet</th><th>Country</th><th>Updated</th><th>Relevant URLs</th><th>Problem</th></tr>${neu}</table></details>` +
      `<details><summary>Latest pipeline log entries (import / translation)</summary><table>${log}</table></details>`;
    abschnitteAktualisieren(d);
    punkt.className = live ? 'live-punkt an' : 'live-punkt aus';
    punkt.textContent = live ? ' ● live · ' + (d.zeit || '').slice(11) : ' ○ snapshot from the last build (' + (d.zeit || '').slice(11, 16) + ') – open http://127.0.0.1:8765/dashboard.html for live updates';
  }
  function neueVersion(d) {
    if (!d.dashboard_version || d.dashboard_version === String(BAU_ZEIT)) return;   // andere Kennung = neu gebaute Seite
    const zoom = document.body.classList.contains('hat-gross');
    if (window.scrollY < 150 && !zoom) { location.reload(); return; }
    banner.hidden = false;
  }
  let fehler = 0;
  async function abfragen() {
    try {
      const r = await fetch('live.json', {cache: 'no-store'});
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      fehler = 0; render(d, true); neueVersion(d);
    } catch (e) {
      fehler++;
      if (fehler === 1) render(LIVE0, false);
      if (fehler >= 3 && fehler % 24 === 0 && window.scrollY < 150) location.reload();   // ohne Server: alle ~2 min neu laden
    }
  }
  render(LIVE0, false);
  abfragen(); setInterval(abfragen, 5000);
})();
