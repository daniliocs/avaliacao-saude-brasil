/**
 * site/assets/js/map.js
 * 
 * Mapa Coroplético e Controle de Visualização Territorial (Leaflet)
 * - Carrega data/releases/latest/mapa_resumo.json (5.570 municípios)
 * - Suporte a camadas: Nota Geral, D1, D2, D3
 * - Botões de zoom no canto inferior direito (bottomright)
 * - Marcadores numéricos visíveis no mapa para os 27 Estados (UFs) e as 27 Capitais
 * - Modal de Rankings com 4 escopos separados: Top 100 Brasil, Por Estado (isolado), 27 Estados e 27 Capitais
 */

import { openDrawer, refreshDrawerIndexMode } from "./drawer_municipio.js?v=0.7.4";
import { updateCompareData } from "./compare_view.js?v=0.7.4";

let leafletMap = null;
let canvasRenderer = null;
let highlightLayer = null;
let mapaResumoData = {};
let rankingsData = {};
let activeIndexMode = "oficial"; // 'oficial' | 'urgencia' | 'integrado'
let activeLayerKey = "nota_geral"; // 'nota_geral' | 'd1_nota' | 'd2_nota' | 'd3_nota' | 'd5_nota' | 'escore_oncologia'
let activeRankDim = "nota_geral";  // 'nota_geral' | 'nota_com_urgencia' | 'd1_nota' | 'd2_nota' | 'd3_nota' | 'd5_nota' | 'escore_oncologia'
let activeRankScope = "brasil";    // 'brasil' | 'brasil_piores' | 'uf' | 'estados' | 'capitais'
let activeMarkerMode = "none";     // 'none' | 'estados' | 'capitais'
let geoJsonLayer = null;
let overlayMarkersLayer = null;

const UF_CENTERS = {
    "AC": [-9.02, -70.81, 7], "AL": [-9.57, -36.78, 8], "AM": [-3.41, -65.85, 6],
    "AP": [1.41, -51.77, 7], "BA": [-12.57, -41.70, 6], "CE": [-5.49, -39.32, 7],
    "DF": [-15.83, -47.86, 10], "ES": [-19.18, -40.30, 8], "GO": [-15.93, -50.14, 7],
    "MA": [-5.42, -45.44, 6], "MG": [-18.51, -44.55, 6], "MS": [-20.77, -54.78, 6],
    "MT": [-12.68, -55.42, 6], "PA": [-3.79, -52.48, 6], "PB": [-7.24, -36.78, 8],
    "PE": [-8.28, -37.86, 7], "PI": [-7.71, -42.72, 6], "PR": [-24.89, -51.55, 7],
    "RJ": [-22.25, -42.66, 8], "RN": [-5.81, -36.59, 8], "RO": [-10.83, -63.34, 7],
    "RR": [2.73, -61.30, 6], "RS": [-30.01, -53.48, 7], "SC": [-27.33, -50.44, 7],
    "SE": [-10.57, -37.38, 9], "SP": [-22.19, -48.79, 7], "TO": [-10.25, -48.25, 6]
};

export async function initMap(metaConfig) {
    console.log("[map.js] Inicializando mapa interativo...");

    if (typeof L === "undefined") {
        console.error("[map.js] Leaflet (L) não está definido.");
        return;
    }

    const mapElement = document.getElementById("leaflet-map");
    if (!mapElement) {
        console.error("[map.js] Contêiner #leaflet-map ausente.");
        return;
    }

    if (leafletMap) {
        leafletMap.remove();
        leafletMap = null;
    }

    // Renderizador Canvas Otimizado:
    // padding: 0.5 expande a área de desenho em 50% além do viewport em todas as direções,
    // eliminando completamente o corte/truncamento de polígonos durante transições de zoom e pan.
    canvasRenderer = L.canvas({
        padding: 0.5,
        tolerance: 3
    });

    // 1. Inicializa o objeto Leaflet centrado no Brasil com controle de zoom fluido e debounce
    leafletMap = L.map("leaflet-map", {
        center: [-14.235, -51.925],
        zoom: 4,
        minZoom: 3,
        maxZoom: 18,
        zoomControl: false,
        renderer: canvasRenderer,
        preferCanvas: true,
        wheelPxPerZoomLevel: 100, // Zoom de scroll mais controlado e fluido
        wheelDebounceTime: 40,
        zoomAnimation: true,
        fadeAnimation: true
    });

    // Pane dedicado para destaque (highlight) em SVG (evita repintar todos os 5.570 municípios no canvas)
    leafletMap.createPane("highlightPane");
    const hPane = leafletMap.getPane("highlightPane");
    if (hPane) {
        hPane.style.zIndex = "650";
        hPane.style.pointerEvents = "none";
    }

    highlightLayer = L.geoJSON(null, {
        pane: "highlightPane",
        style: {
            weight: 2.8,
            color: "#0369a1",
            fillColor: "#0284c7",
            fillOpacity: 0.4
        }
    }).addTo(leafletMap);

    leafletMap.on("zoomstart movestart", () => {
        if (highlightLayer) highlightLayer.clearLayers();
    });

    leafletMap.on("zoomend moveend", () => {
        if (highlightLayer) highlightLayer.clearLayers();
    });

    L.control.zoom({ position: "bottomright" }).addTo(leafletMap);
    overlayMarkersLayer = L.layerGroup().addTo(leafletMap);

    // 2. Camadas de Mapa Base
    const googlePadrao = L.tileLayer(
        "https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}&hl=pt-BR",
        {
            subdomains: ["0", "1", "2", "3"],
            attribution: "Dados do mapa &copy; Google",
            maxZoom: 20
        }
    );

    const googleTerreno = L.tileLayer(
        "https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}&hl=pt-BR",
        {
            subdomains: ["0", "1", "2", "3"],
            attribution: "Dados do mapa &copy; Google Relevo",
            maxZoom: 20
        }
    );

    const googleHibrido = L.tileLayer(
        "https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}&hl=pt-BR",
        {
            subdomains: ["0", "1", "2", "3"],
            attribution: "Imagens &copy; Google Satélite",
            maxZoom: 20
        }
    );

    const openStreetMap = L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }
    );

    googlePadrao.addTo(leafletMap);

    const baseMaps = {
        "Google Maps (Padrão)": googlePadrao,
        "Google Maps (Relevo)": googleTerreno,
        "Google Maps (Satélite)": googleHibrido,
        "OpenStreetMap": openStreetMap
    };
    L.control.layers(baseMaps, null, { position: "topright" }).addTo(leafletMap);

    setTimeout(() => {
        if (leafletMap) leafletMap.invalidateSize();
    }, 150);

    // 3. Configura controles de busca, filtros, seletor de modelo, camada, marcadores, rankings, layout e modal de info
    setupIndexModeSelector();
    setupLayerSelector();
    setupMarkerModeSelector();
    setupSearchAndFilters();
    setupRankingsModal();
    setupInfoModal();
    setupLayoutControls();

    // 4. Carrega os dados e malha de forma assíncrona
    Promise.all([loadMapaResumo(), loadRankings()]).then(() => {
        setupSearchAndFilters();
        updateCompareData(mapaResumoData, rankingsData);
        renderMapOverlayMarkers();
        return loadGeoBoundary();
    }).catch(err => {
        console.error("[map.js] Erro ao carregar dados territoriais:", err);
    });
}

async function loadRankings() {
    const candidatePaths = [
        "data/releases/latest/rankings_resumo.json?v=0.7.4",
        "./data/releases/latest/rankings_resumo.json?v=0.7.4",
        "../data/releases/latest/rankings_resumo.json?v=0.7.4"
    ];

    for (const path of candidatePaths) {
        try {
            const response = await fetch(path);
            if (response.ok) {
                rankingsData = await response.json();
                console.log(`[map.js] rankings_resumo.json carregado com sucesso (${path}).`);
                return;
            }
        } catch (e) {
            // Continua para o próximo
        }
    }
    console.warn("[map.js] Rankings não disponíveis no momento.");
}

async function loadMapaResumo() {
    const candidatePaths = [
        "data/releases/latest/mapa_resumo.json?v=0.7.4",
        "./data/releases/latest/mapa_resumo.json?v=0.7.4",
        "../data/releases/latest/mapa_resumo.json?v=0.7.4"
    ];

    for (const path of candidatePaths) {
        try {
            const response = await fetch(path);
            if (response.ok) {
                mapaResumoData = await response.json();
                console.log(`[map.js] ${Object.keys(mapaResumoData).length} municípios carregados (${path}).`);
                return;
            }
        } catch (err) {
            // Continua para o próximo
        }
    }
    console.error("[map.js] Falha crítica ao obter mapa_resumo.json em todos os caminhos.");
}

async function loadGeoBoundary() {
    const geoPaths = [
        "assets/geo/br_municipios.json",
        "./assets/geo/br_municipios.json",
        "site/assets/geo/br_municipios.json",
        "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-100-mun.json"
    ];

    for (const path of geoPaths) {
        try {
            console.log(`[map.js] Buscando malha vetorial: ${path}...`);
            const res = await fetch(path);
            if (res.ok) {
                const geoData = await res.json();
                console.log(`[map.js] Malha geográfica carregada com sucesso a partir de ${path}`);
                renderGeoJson(geoData);
                const loader = document.getElementById("map-loading");
                if (loader) loader.classList.add("hidden");
                return;
            }
        } catch (e) {
            console.warn(`[map.js] Erro ao carregar malha de ${path}:`, e);
        }
    }

    const loader = document.getElementById("map-loading");
    if (loader) {
        const text = document.getElementById("map-loading-text");
        if (text) text.textContent = "Busca de municípios e Rankings prontos!";
        setTimeout(() => loader.classList.add("hidden"), 2500);
    }
}

function getTooltipHtml(mun) {
    const popFmt = mun.populacao ? mun.populacao.toLocaleString("pt-BR") + " hab." : "População em validação";
    let notaExibida = mun.nota_geral;
    let titleBadge = `Nota Geral (3D): ${mun.nota_geral !== null && mun.nota_geral !== undefined ? mun.nota_geral.toFixed(1) : '—'} / 100`;
    let posNac = mun.posicao_nacional;
    let posEst = mun.posicao_estadual;

    if (activeLayerKey === "escore_oncologia") {
        notaExibida = mun.escore_oncologia;
        const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
        titleBadge = `🎗️ Oncologia (CACON/UNACON): ${fmt} / 100`;
        posNac = mun.rank_onco || null;
    } else if (activeLayerKey === "d5_nota") {
        notaExibida = mun.d5_nota;
        const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
        titleBadge = `🚑 D5: Urgência & SAMU 192: ${fmt} / 100`;
    } else if (activeLayerKey === "d1_nota") {
        notaExibida = mun.d1_nota;
        const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
        titleBadge = `📊 D1: Resultados em Saúde: ${fmt} / 100`;
    } else if (activeLayerKey === "d2_nota") {
        notaExibida = mun.d2_nota;
        const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
        titleBadge = `🩺 D2: Atenção Primária: ${fmt} / 100`;
    } else if (activeLayerKey === "d3_nota") {
        notaExibida = mun.d3_nota;
        const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
        titleBadge = `🏥 D3: Estrutura & Capacidade: ${fmt} / 100`;
    } else {
        // activeLayerKey === "nota_geral" -> obedece o modo selecionado (oficial, urgencia, integrado)
        if (activeIndexMode === "integrado") {
            notaExibida = (mun.nota_integrada !== null && mun.nota_integrada !== undefined) ? mun.nota_integrada : mun.nota_geral;
            const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
            titleBadge = `Nota Integrada (10% Onco): ${fmt} / 100`;
            posNac = mun.posicao_nacional_integrada || mun.posicao_nacional;
            posEst = mun.posicao_estadual_integrada || mun.posicao_estadual;
        } else if (activeIndexMode === "urgencia") {
            notaExibida = (mun.nota_com_urgencia !== null && mun.nota_com_urgencia !== undefined) ? mun.nota_com_urgencia : mun.nota_geral;
            const fmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : '—';
            titleBadge = `Nota c/ Urgência (15% RUE): ${fmt} / 100`;
            posNac = mun.posicao_nacional_urgencia || mun.posicao_nacional;
            posEst = mun.posicao_estadual_urgencia || mun.posicao_estadual;
        }
    }

    const escoreFmt = notaExibida !== null && notaExibida !== undefined ? notaExibida.toFixed(1) : null;
    const corNota = getColorForScore(notaExibida);
    const urg = mun.urgencia_samu;

    let statusBlock = "";
    if (escoreFmt) {

        statusBlock = `
            <div style="margin: 4px 0 6px 0;">
                <span style="background:${corNota}; color:#ffffff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.875rem; display:inline-block;">
                    ${titleBadge}
                </span>
            </div>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:4px 6px; margin-bottom:6px; font-size:0.75rem;">
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                    <span><strong>D1</strong> Resultados:</span>
                    <strong style="color:${getColorForScore(mun.d1_nota)}">${mun.d1_nota !== null && mun.d1_nota !== undefined ? mun.d1_nota.toFixed(1) : '—'}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                    <span><strong>D2</strong> Primária:</span>
                    <strong style="color:${getColorForScore(mun.d2_nota)}">${mun.d2_nota !== null && mun.d2_nota !== undefined ? mun.d2_nota.toFixed(1) : '—'}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                    <span><strong>D3</strong> Estrutura:</span>
                    <strong style="color:${getColorForScore(mun.d3_nota)}">${mun.d3_nota !== null && mun.d3_nota !== undefined ? mun.d3_nota.toFixed(1) : '—'}</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span><strong>D5</strong> Urgência &amp; SAMU:</span>
                    <strong style="color:${getColorForScore(mun.d5_nota)}">${mun.d5_nota !== null && mun.d5_nota !== undefined ? mun.d5_nota.toFixed(1) : '—'}</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span><strong>🎗️</strong> Oncologia (CACON):</span>
                    <strong style="color:${getColorForScore(mun.escore_oncologia)}">${mun.escore_oncologia !== null && mun.escore_oncologia !== undefined ? mun.escore_oncologia.toFixed(1) : '—'}</strong>
                </div>
            </div>
            <div style="font-size:0.78rem; line-height:1.45; color:#334155;">
                <span>🏆 Ranking Nacional: <strong>#${posNac ? posNac.toLocaleString("pt-BR") : '—'}</strong> de 5.570</span><br>
                <span>🥇 Ranking Estadual (${mun.uf}): <strong>#${posEst ? posEst.toLocaleString("pt-BR") : '—'}</strong> de ${(mun.total_uf || '—').toLocaleString("pt-BR")}</span><br>
                ${urg ? `<span>🚑 SAMU: <strong>${urg.cob_samu_efetiva}%</strong> &bull; Região: <strong>${urg.usb_reg ?? 0} USB / ${urg.usa_reg ?? 0} USA</strong></span><br><span>⏱️ Polo Hospitalar: <strong>${urg.dist_polo_km === 0 ? 'Sede Local (0 km)' : `${urg.dist_polo_km} km (~${urg.tempo_ambulancia_min} min — ${urg.polo_hospitalar_ref})`}</strong></span><br>` : ''}
                ${mun.oncologia_tfd ? `<span>🎗️ CACON: <strong>${mun.oncologia_tfd.eh_polo_onco ? 'Polo Local' : `${mun.oncologia_tfd.dist_cacon_km} km (${mun.oncologia_tfd.cacon_referencia})`}</strong> &bull; Lei 60d: <strong>${mun.oncologia_tfd.pct_60d_onco}%</strong></span><br>` : ''}
                <span>🏥 Região de Saúde: <strong>${mun.regiao_saude || '—'}</strong></span>
            </div>
        `;
    } else {
        statusBlock = `<span style="color:#d97706; font-weight:700;">Status: Sem Classificação</span><br>`;
    }

    return `
        <div style="font-size:0.8125rem; line-height:1.45; min-width:220px; padding:2px;">
            <strong style="font-size:1rem; color:#0f172a;">${mun.nome} (${mun.uf || ''})</strong><br>
            <span style="color:#475569;">👥 População: <strong>${popFmt}</strong></span><br>
            ${statusBlock}
            <span style="color:#0284c7; font-size:0.75rem; font-weight:600; display:block; margin-top:4px;">👉 Clique para abrir a ficha completa</span>
        </div>
    `;
}

function renderGeoJson(geoData) {
    if (geoJsonLayer) {
        leafletMap.removeLayer(geoJsonLayer);
    }

    geoJsonLayer = L.geoJSON(geoData, {
        renderer: canvasRenderer,
        smoothFactor: 1.2,
        style: styleFeature,
        onEachFeature: (feature, layer) => {
            const ibge = feature.properties?.id || feature.properties?.codarea || feature.properties?.ibge7;
            const mun = mapaResumoData[ibge] || { nome: feature.properties?.name || "Município", ibge7: ibge };

            // Tooltip sob demanda via função (afastado 24px do cursor para não cobrir o polígono do município)
            layer.bindTooltip(() => getTooltipHtml(mun), {
                sticky: true,
                offset: [24, -15],
                direction: "auto"
            });

            layer.on({
                click: () => openDrawer(mun, activeIndexMode),
                mouseover: (e) => {
                    // Destaque instantâneo no highlightPane SVG (0 repinturas no canvas principal)
                    if (highlightLayer && e.target.feature) {
                        highlightLayer.clearLayers();
                        highlightLayer.addData(e.target.feature);
                    }
                },
                mouseout: () => {
                    if (highlightLayer) {
                        highlightLayer.clearLayers();
                    }
                }
            });
        }
    }).addTo(leafletMap);
}

function styleFeature(feature) {
    const ibge = feature.properties?.id || feature.properties?.codarea || feature.properties?.ibge7;
    const mun = mapaResumoData[ibge];

    let fieldKey = activeLayerKey;
    if (activeLayerKey === "nota_geral") {
        if (activeIndexMode === "integrado") {
            fieldKey = "nota_integrada";
        } else if (activeIndexMode === "urgencia") {
            fieldKey = "nota_com_urgencia";
        }
    }

    if (!mun || mun.status === "sem_classificacao" || mun[fieldKey] === null || mun[fieldKey] === undefined) {
        return {
            fillColor: "#94a3b8",
            weight: 0.6,
            opacity: 0.9,
            color: "#475569",
            dashArray: "2, 2",
            fillOpacity: 0.35
        };
    }

    const val = mun[fieldKey];
    return {
        fillColor: getColorForScore(val),
        weight: 0.5,
        opacity: 0.9,
        color: "#ffffff",
        fillOpacity: 0.65
    };
}

function getColorForScore(score) {
    if (score === null || score === undefined) return "#cbd5e1";
    if (score >= 80) return "#15803d";
    if (score >= 65) return "#22c55e";
    if (score >= 50) return "#eab308";
    if (score >= 35) return "#f97316";
    return "#dc2626";
}

function updateIndexModeSelectorState() {
    const indexModeSelector = document.querySelector(".index-mode-selector");
    if (indexModeSelector) {
        indexModeSelector.classList.toggle("is-dim-active", activeLayerKey !== "nota_geral");
    }
}

function setupIndexModeSelector() {
    const modeButtons = document.querySelectorAll(".index-mode-btn");
    modeButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            // Se clicar em um dos modos da Nota Geral enquanto visualiza outra dimensão,
            // reativa automaticamente a visualização de 'Nota Geral' para conveniência
            if (activeLayerKey !== "nota_geral") {
                activeLayerKey = "nota_geral";
                document.querySelectorAll(".layer-btn").forEach((lb) => {
                    lb.classList.toggle("active", lb.dataset.layer === "nota_geral");
                });
            }
            modeButtons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            activeIndexMode = btn.dataset.indexMode || "oficial";
            updateIndexModeSelectorState();
            if (geoJsonLayer) {
                geoJsonLayer.setStyle(styleFeature);
            }
            renderMapOverlayMarkers();
            refreshDrawerIndexMode(activeIndexMode);
        });
    });
    updateIndexModeSelectorState();
}

function setupLayerSelector() {
    const layerButtons = document.querySelectorAll(".layer-btn");
    layerButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            layerButtons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            activeLayerKey = btn.dataset.layer;
            updateIndexModeSelectorState();
            if (geoJsonLayer) {
                geoJsonLayer.setStyle(styleFeature);
            }
            renderMapOverlayMarkers();
        });
    });
    updateIndexModeSelectorState();
}

function setMarkerMode(mode) {
    activeMarkerMode = mode;
    document.querySelectorAll(".marker-mode-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.markerMode === mode);
    });
    renderMapOverlayMarkers();
}

function setupMarkerModeSelector() {
    const btns = document.querySelectorAll(".marker-mode-btn");
    btns.forEach(btn => {
        btn.addEventListener("click", () => {
            setMarkerMode(btn.dataset.markerMode || "none");
        });
    });
}

function renderMapOverlayMarkers() {
    if (!overlayMarkersLayer || !leafletMap) return;
    overlayMarkersLayer.clearLayers();

    if (activeMarkerMode === "none") return;

    const ufDimFieldMap = {
        "nota_geral": activeIndexMode === "integrado" ? "media_integrada_uf" : (activeIndexMode === "urgencia" ? "media_com_urgencia_uf" : "media_escore_uf"),
        "nota_integrada": "media_integrada_uf",
        "d1_nota": "media_d1_uf",
        "d2_nota": "media_d2_uf",
        "d3_nota": "media_d3_uf",
        "d5_nota": "media_d5_uf",
        "escore_oncologia": "media_onco_uf",
        "nota_com_urgencia": "media_com_urgencia_uf"
    };

    if (activeMarkerMode === "estados") {
        const estados = rankingsData?.ranking_estados || [];
        const field = ufDimFieldMap[activeLayerKey] || (activeIndexMode === "urgencia" ? "media_com_urgencia_uf" : "media_escore_uf");
        const sorted = [...estados].sort((a, b) => (b[field] || 0) - (a[field] || 0));

        sorted.forEach((est, idx) => {
            const val = est[field];
            if (val === null || val === undefined) return;
            const color = getColorForScore(val);
            const icon = L.divIcon({
                className: "map-numeric-pin-wrapper",
                html: `
                    <div class="map-numeric-pin" style="border-color:${color};">
                        <span class="map-numeric-pin__label">${est.uf}</span>
                        <span class="map-numeric-pin__val" style="background:${color};">${val.toFixed(1)}</span>
                    </div>
                `,
                iconSize: [74, 26],
                iconAnchor: [37, 13]
            });

            const marker = L.marker([est.lat, est.lng], { icon, zIndexOffset: 900 });
            let estScoreLabel = `Média Oficial (3D): <strong>${est.media_escore_uf.toFixed(1)} pts</strong>`;
            if (activeLayerKey === "escore_oncologia") {
                estScoreLabel = `🎗️ Média Oncologia: <strong>${est.media_onco_uf ? est.media_onco_uf.toFixed(1) : '—'} pts</strong>`;
            } else if (activeLayerKey === "d5_nota") {
                estScoreLabel = `🚑 Média Urgência & SAMU: <strong>${est.media_d5_uf ? est.media_d5_uf.toFixed(1) : '—'} pts</strong>`;
            } else if (activeLayerKey === "d1_nota") {
                estScoreLabel = `📊 Média D1 Resultados: <strong>${est.media_d1_uf.toFixed(1)} pts</strong>`;
            } else if (activeLayerKey === "d2_nota") {
                estScoreLabel = `🩺 Média D2 Primária: <strong>${est.media_d2_uf.toFixed(1)} pts</strong>`;
            } else if (activeLayerKey === "d3_nota") {
                estScoreLabel = `🏥 Média D3 Estrutura: <strong>${est.media_d3_uf.toFixed(1)} pts</strong>`;
            } else if (activeIndexMode === "integrado") {
                estScoreLabel = `🎗️⚡ Média Integrada (10% Onco): <strong>${est.media_integrada_uf ? est.media_integrada_uf.toFixed(1) : '—'} pts</strong>`;
            } else if (activeIndexMode === "urgencia") {
                estScoreLabel = `⚡ Média c/ Urgência (15%): <strong>${est.media_com_urgencia_uf ? est.media_com_urgencia_uf.toFixed(1) : '—'} pts</strong>`;
            }

            marker.bindTooltip(`
                <div style="font-size:0.8rem; line-height:1.45; min-width:190px;">
                    <strong style="font-size:0.95rem;">#${idx + 1}º ${est.nome_uf} (${est.uf})</strong><br>
                    <span>${estScoreLabel}</span><br>
                    <span>D1: <strong>${est.media_d1_uf.toFixed(1)}</strong> | D2: <strong>${est.media_d2_uf.toFixed(1)}</strong> | D3: <strong>${est.media_d3_uf.toFixed(1)}</strong> | D5: <strong>${est.media_d5_uf ? est.media_d5_uf.toFixed(1) : '—'}</strong> | Onco: <strong>${est.media_onco_uf ? est.media_onco_uf.toFixed(1) : '—'}</strong></span><br>
                    <span>Municípios: <strong>${est.total_municipios}</strong> &bull; SAMU: <strong>${est.cob_samu_media_uf ?? '—'}%</strong> &bull; UPAs: <strong>${est.total_upas_uf ?? 0}</strong></span><br>
                    <span style="color:#0284c7; font-weight:600;">👉 Clique para focar no Estado e ver o ranking da UF</span>
                </div>
            `, { direction: "top", offset: [0, -10] });

            marker.on("click", () => {
                const ufFilter = document.getElementById("uf-filter");
                if (ufFilter) {
                    ufFilter.value = est.uf;
                    ufFilter.dispatchEvent(new Event("change"));
                }
                activeRankScope = "uf";
                syncScopeTabs();
                renderRankingsContent(est.uf);
                const modalRanking = document.getElementById("rankings-modal");
                if (modalRanking) modalRanking.classList.add("active");
            });

            marker.addTo(overlayMarkersLayer);
        });
    } else if (activeMarkerMode === "capitais") {
        const capitais = rankingsData?.ranking_capitais || [];
        let field = activeLayerKey;
        if (activeLayerKey === "nota_geral") {
            if (activeIndexMode === "integrado") {
                field = "nota_integrada";
            } else if (activeIndexMode === "urgencia") {
                field = "nota_com_urgencia";
            } else {
                field = "nota_geral";
            }
        }
        const sorted = [...capitais].sort((a, b) => {
            const valA = a[field] ?? a.nota_geral ?? a.escore ?? 0;
            const valB = b[field] ?? b.nota_geral ?? b.escore ?? 0;
            return valB - valA;
        });

        sorted.forEach((cap, idx) => {
            const val = cap[field] ?? cap.nota_geral ?? cap.escore;
            if (val === null || val === undefined) return;
            const color = getColorForScore(val);
            const shortName = cap.nome.length > 12 ? cap.nome.slice(0, 11) + "." : cap.nome;
            const icon = L.divIcon({
                className: "map-numeric-pin-wrapper",
                html: `
                    <div class="map-numeric-pin map-numeric-pin--cap" style="border-color:${color};">
                        <span class="map-numeric-pin__label">${shortName}</span>
                        <span class="map-numeric-pin__val" style="background:${color};">${val.toFixed(1)}</span>
                    </div>
                `,
                iconSize: [98, 26],
                iconAnchor: [49, 13]
            });

            const marker = L.marker([cap.lat, cap.lng], { icon, zIndexOffset: 950 });
            let scoreLabel = "";
            if (activeLayerKey === "escore_oncologia") {
                scoreLabel = `🎗️ Escore Oncologia: <strong>${(cap.escore_oncologia ?? 0).toFixed(1)} / 100</strong> (${cap.polo_tipo_centro || 'CACON/UNACON'})`;
            } else if (activeLayerKey === "d5_nota") {
                scoreLabel = `🚑 D5 Urgência & SAMU: <strong>${(cap.d5_nota ?? 0).toFixed(1)} / 100</strong>`;
            } else if (activeLayerKey === "d1_nota") {
                scoreLabel = `📊 D1 Resultados em Saúde: <strong>${(cap.d1_nota ?? 0).toFixed(1)} / 100</strong>`;
            } else if (activeLayerKey === "d2_nota") {
                scoreLabel = `🩺 D2 Atenção Primária: <strong>${(cap.d2_nota ?? 0).toFixed(1)} / 100</strong>`;
            } else if (activeLayerKey === "d3_nota") {
                scoreLabel = `🏥 D3 Estrutura Hospitalar: <strong>${(cap.d3_nota ?? 0).toFixed(1)} / 100</strong>`;
            } else if (activeIndexMode === "integrado" && cap.nota_integrada !== null && cap.nota_integrada !== undefined) {
                scoreLabel = `Nota Integrada (10% Onco): <strong>${cap.nota_integrada.toFixed(1)} / 100</strong> (#${cap.posicao_nacional_integrada || '—'}º BR)`;
            } else if (activeIndexMode === "urgencia" && cap.nota_com_urgencia !== null && cap.nota_com_urgencia !== undefined) {
                scoreLabel = `Nota c/ Urgência (15%): <strong>${cap.nota_com_urgencia.toFixed(1)} / 100</strong> (#${cap.posicao_nacional_urgencia || '—'}º BR)`;
            } else {
                scoreLabel = `Nota Geral Oficial (3D): <strong>${(cap.nota_geral ?? cap.escore).toFixed(1)} / 100</strong> (#${cap.posicao_nacional || '—'}º BR)`;
            }

            marker.bindTooltip(`
                <div style="font-size:0.8rem; line-height:1.45; min-width:195px;">
                    <strong style="font-size:0.95rem;">🏙️ #${idx + 1}ª Capital: ${cap.nome} (${cap.uf})</strong><br>
                    <span>${scoreLabel}</span><br>
                    <span>D1: <strong>${cap.d1_nota.toFixed(1)}</strong> | D2: <strong>${cap.d2_nota.toFixed(1)}</strong> | D3: <strong>${cap.d3_nota.toFixed(1)}</strong> | D5: <strong>${cap.d5_nota ? cap.d5_nota.toFixed(1) : '—'}</strong></span><br>
                    <span>População: <strong>${cap.populacao ? cap.populacao.toLocaleString("pt-BR") : '—'} hab.</strong> &bull; SAMU: <strong>${cap.cob_samu_efetiva ?? '—'}%</strong></span><br>
                    <span style="color:#0284c7; font-weight:600;">👉 Clique para abrir a ficha completa da Capital</span>
                </div>
            `, { direction: "top", offset: [0, -10] });

            marker.on("click", () => {
                const mun = mapaResumoData[cap.ibge7];
                if (mun) openDrawer(mun, activeIndexMode);
            });

            marker.addTo(overlayMarkersLayer);
        });
    }
}

function setupLayoutControls() {
    const btnExpand = document.getElementById("btn-toggle-map-expand");
    const btnRestore = document.getElementById("btn-restore-menus");
    const btnFloatingRank = document.getElementById("btn-floating-ranking");
    const btnToggleLegend = document.getElementById("btn-toggle-legend");
    const legendEl = document.getElementById("map-legend");

    function setMapExpanded(expanded) {
        if (expanded) {
            document.body.classList.add("map-expanded");
            if (btnExpand) {
                btnExpand.innerHTML = "🔼 Ocultar Menus";
                btnExpand.title = "Restaurar menus superiores";
            }
        } else {
            document.body.classList.remove("map-expanded");
            if (btnExpand) {
                btnExpand.innerHTML = "⛶ Expandir Mapa";
                btnExpand.title = "Ocultar cabeçalho e menus para maximizar o mapa na tela";
            }
        }
        setTimeout(() => {
            if (leafletMap) leafletMap.invalidateSize();
        }, 180);
    }

    if (btnExpand) {
        btnExpand.addEventListener("click", () => {
            const isExp = document.body.classList.contains("map-expanded");
            setMapExpanded(!isExp);
        });
    }

    if (btnRestore) {
        btnRestore.addEventListener("click", () => {
            setMapExpanded(false);
        });
    }

    if (btnFloatingRank) {
        btnFloatingRank.addEventListener("click", () => {
            const modalRanking = document.getElementById("rankings-modal");
            if (modalRanking) {
                modalRanking.classList.add("active");
                renderRankingsContent();
            }
        });
    }

    if (btnToggleLegend && legendEl) {
        btnToggleLegend.addEventListener("click", (e) => {
            e.stopPropagation();
            legendEl.classList.toggle("minimized");
            const isMin = legendEl.classList.contains("minimized");
            btnToggleLegend.textContent = isMin ? "+" : "−";
            btnToggleLegend.title = isMin ? "Expandir legenda" : "Minimizar legenda";
        });
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.body.classList.contains("map-expanded")) {
            setMapExpanded(false);
        }
    });
}

function focusMunicipalityOnMap(ibge7) {
    if (!geoJsonLayer || !leafletMap) return;
    geoJsonLayer.eachLayer(layer => {
        const id = layer.feature?.properties?.id || layer.feature?.properties?.codarea || layer.feature?.properties?.ibge7;
        if (id === ibge7) {
            if (highlightLayer && layer.feature) {
                highlightLayer.clearLayers();
                highlightLayer.addData(layer.feature);
            }
            try {
                const bounds = layer.getBounds();
                leafletMap.fitBounds(bounds, { maxZoom: 9, padding: [40, 40] });
            } catch (e) {
                // ignora se bounds não puderem ser calculados
            }
        }
    });
}

function setupSearchAndFilters() {
    const searchInput = document.getElementById("search-municipio-input");
    const dropdown = document.getElementById("search-results-dropdown");
    const ufFilter = document.getElementById("uf-filter");
    const modalUfSelect = document.getElementById("modal-uf-select");

    const ufs = Object.keys(UF_CENTERS).sort();

    if (ufFilter && ufFilter.options.length <= 1) {
        ufs.forEach(uf => {
            const opt = document.createElement("option");
            opt.value = uf;
            opt.textContent = uf;
            ufFilter.appendChild(opt);
        });

        ufFilter.addEventListener("change", () => {
            const selectedUf = ufFilter.value;
            if (modalUfSelect && modalUfSelect.value !== selectedUf) {
                modalUfSelect.value = selectedUf || "SP";
            }
            if (selectedUf) {
                const centerCfg = UF_CENTERS[selectedUf];
                if (centerCfg && leafletMap) {
                    leafletMap.setView([centerCfg[0], centerCfg[1]], centerCfg[2]);
                }
                activeRankScope = "uf";
                syncScopeTabs();
                renderRankingsContent(selectedUf);
            } else if (leafletMap) {
                leafletMap.setView([-14.235, -51.925], 4);
                activeRankScope = "brasil";
                syncScopeTabs();
                renderRankingsContent("");
            }
        });
    }

    if (modalUfSelect && modalUfSelect.options.length === 0) {
        ufs.forEach(uf => {
            const opt = document.createElement("option");
            opt.value = uf;
            opt.textContent = uf;
            modalUfSelect.appendChild(opt);
        });
        modalUfSelect.value = ufFilter?.value || "SP";

        modalUfSelect.addEventListener("change", () => {
            const chosenUf = modalUfSelect.value;
            if (ufFilter) {
                ufFilter.value = chosenUf;
                const centerCfg = UF_CENTERS[chosenUf];
                if (centerCfg && leafletMap) {
                    leafletMap.setView([centerCfg[0], centerCfg[1]], centerCfg[2]);
                }
            }
            renderRankingsContent(chosenUf);
        });
    }

    if (!searchInput || !dropdown || searchInput.dataset.initialized === "true") return;
    searchInput.dataset.initialized = "true";

    let debounceTimer;
    searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        const query = searchInput.value.trim().toLowerCase();
        
        if (query.length < 2) {
            dropdown.innerHTML = "";
            dropdown.classList.remove("visible");
            return;
        }

        debounceTimer = setTimeout(() => {
            const results = Object.values(mapaResumoData)
                .filter(m => 
                    m.nome && (
                        m.nome.toLowerCase().includes(query) ||
                        m.ibge7.includes(query) ||
                        (m.ibge6 && m.ibge6.includes(query))
                    )
                )
                .slice(0, 15);

            if (results.length === 0) {
                dropdown.innerHTML = `<div class="search-item" style="color: var(--color-text-subtle);">Nenhum município encontrado</div>`;
            } else {
                dropdown.innerHTML = results.map(m => `
                    <div class="search-item" data-ibge="${m.ibge7}">
                        <strong>${m.nome} (${m.uf})</strong>
                        <span style="font-size: 0.75rem; color: var(--color-text-subtle);">Nota: ${m.nota_geral ? m.nota_geral.toFixed(1) : '—'} | IBGE: ${m.ibge7}</span>
                    </div>
                `).join("");

                dropdown.querySelectorAll(".search-item").forEach(item => {
                    item.addEventListener("click", () => {
                        const ibge7 = item.dataset.ibge;
                        const mun = mapaResumoData[ibge7];
                        dropdown.classList.remove("visible");
                        searchInput.value = `${mun.nome} (${mun.uf})`;
                        focusMunicipalityOnMap(ibge7);
                        openDrawer(mun, activeIndexMode);
                    });
                });
            }
            dropdown.classList.add("visible");
        }, 150);
    });

    document.addEventListener("click", (e) => {
        if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove("visible");
        }
    });
}

function syncScopeTabs() {
    document.querySelectorAll(".rank-scope-btn").forEach(btn => {
        const scope = btn.dataset.rankScope || btn.getAttribute("data-rank-scope");
        btn.classList.toggle("active", scope === activeRankScope);
    });
    const ufWrap = document.getElementById("modal-uf-selector-wrap");
    if (ufWrap) {
        ufWrap.style.display = activeRankScope === "uf" ? "flex" : "none";
    }
}

function setupRankingsModal() {
    const btnRanking = document.getElementById("btn-toggle-ranking");
    const modalRanking = document.getElementById("rankings-modal");
    const btnCloseRank = document.getElementById("btn-close-ranking");
    const rankDimButtons = document.querySelectorAll(".rank-dim-btn");
    const rankScopeButtons = document.querySelectorAll(".rank-scope-btn");

    if (btnRanking && modalRanking) {
        btnRanking.addEventListener("click", () => {
            const ufFilter = document.getElementById("uf-filter");
            const activeUf = ufFilter ? ufFilter.value : "";
            if (activeUf && activeRankScope === "brasil") {
                activeRankScope = "uf";
            }
            syncScopeTabs();
            renderRankingsContent(activeUf);
            modalRanking.classList.add("active");
        });
    }

    if (btnCloseRank && modalRanking) {
        btnCloseRank.addEventListener("click", () => {
            modalRanking.classList.remove("active");
        });
    }

    if (modalRanking) {
        modalRanking.addEventListener("click", (e) => {
            if (e.target === modalRanking) {
                modalRanking.classList.remove("active");
            }
        });
    }

    rankScopeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            activeRankScope = btn.dataset.rankScope || btn.getAttribute("data-rank-scope") || "brasil";
            syncScopeTabs();
            const ufFilter = document.getElementById("uf-filter");
            const modalUfSelect = document.getElementById("modal-uf-select");
            const chosenUf = ufFilter?.value || modalUfSelect?.value || "SP";
            renderRankingsContent(chosenUf);
        });
    });

    rankDimButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            rankDimButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeRankDim = btn.dataset.rankDim || "nota_geral";
            const ufFilter = document.getElementById("uf-filter");
            const modalUfSelect = document.getElementById("modal-uf-select");
            const activeUf = ufFilter?.value || modalUfSelect?.value || "SP";
            renderRankingsContent(activeUf);
        });
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modalRanking && modalRanking.classList.contains("active")) {
            modalRanking.classList.remove("active");
        }
    });
}

function setupInfoModal() {
    const btnInfo = document.getElementById("btn-info");
    const modalInfo = document.getElementById("info-modal");
    const btnCloseInfo = document.getElementById("btn-close-info");

    if (btnInfo && modalInfo) {
        btnInfo.addEventListener("click", () => {
            modalInfo.classList.add("active");
        });
    }

    if (btnCloseInfo && modalInfo) {
        btnCloseInfo.addEventListener("click", () => {
            modalInfo.classList.remove("active");
        });
    }

    if (modalInfo) {
        modalInfo.addEventListener("click", (e) => {
            if (e.target === modalInfo) {
                modalInfo.classList.remove("active");
            }
        });
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modalInfo && modalInfo.classList.contains("active")) {
            modalInfo.classList.remove("active");
        }
    });
}

function renderRankingsContent(selectedUf = "") {
    const container = document.getElementById("rankings-modal-body");
    if (!container) return;
    container.scrollTop = 0;

    if (!rankingsData || Object.keys(rankingsData).length === 0) {
        container.innerHTML = `<p style="color:var(--color-text-subtle); padding:1rem;">Carregando rankings oficiais...</p>`;
        return;
    }

    const dimLabelMap = {
        "nota_geral": "Nota Geral Consolidada (D1 + D2 + D3 — Padrão Oficial)",
        "nota_integrada": "Nota Integrada Completa (25% D1 + 25% D2 + 25% D3 + 15% Urgência + 10% Oncologia)",
        "nota_com_urgencia": "Nota Expandida com Urgência e Distância Golden Hour (30% D1 + 25% D2 + 30% D3 + 15% D5)",
        "d1_nota": "D1 — Resultados em Saúde (Mortalidade Infantil, DCNT e Evitáveis)",
        "d2_nota": "D2 — Atenção Primária (ICSAP, Pré-natal 7+ e Vacinação Composta)",
        "d3_nota": "D3 — Acesso e Capacidade (Leitos Regionais, Médicos/Enf. 40h e eSF)",
        "d5_nota": "D5 — Rede de Urgência & SAMU 192 (Cobertura SAMU, UPAs 24h e Frotas)",
        "escore_oncologia": "🎗️ Linha de Cuidado Oncológico & CACON/UNACON (Cumprimento Lei 60 Dias e TFD)"
    };
    const activeLabel = dimLabelMap[activeRankDim] || "Nota Geral Consolidada";
    const allMun = Object.values(mapaResumoData);

    const renderMunicipalityList = (items, isPiores = false, scope = activeRankScope) => {
        if (!items || items.length === 0) {
            return "<p style='color:var(--color-text-subtle);'>Nenhum município listado.</p>";
        }
        return `
            <div style="display:flex; flex-direction:column; gap:0.4rem;">
                ${items.map((m, idx) => {
                    const d1 = typeof m.d1_nota === "number" ? m.d1_nota.toFixed(1) : "—";
                    const d2 = typeof m.d2_nota === "number" ? m.d2_nota.toFixed(1) : "—";
                    const d3 = typeof m.d3_nota === "number" ? m.d3_nota.toFixed(1) : "—";
                    const d5 = typeof m.d5_nota === "number" ? m.d5_nota.toFixed(1) : "—";
                    const score = typeof m[activeRankDim] === "number" ? m[activeRankDim] : (typeof m.escore === "number" ? m.escore : m.nota_geral);
                    const scoreFmt = typeof score === "number" ? score.toFixed(1) : "—";

                    // Posição no país para sinalização adicional
                    const nacPos = (activeRankDim === "nota_integrada" && m.posicao_nacional_integrada)
                        ? m.posicao_nacional_integrada
                        : ((activeRankDim === "nota_com_urgencia" && m.posicao_nacional_urgencia)
                            ? m.posicao_nacional_urgencia
                            : m.posicao_nacional);

                    let posPrefix = "";
                    let posSuffix = "";

                    if (scope === "uf") {
                        // Ranking por Estado: Inicia em 1º para o melhor do estado
                        posPrefix = `<span style="font-weight:700; color:var(--color-primary-dark); margin-right:4px;">#${idx + 1}º</span>`;
                        if (nacPos) {
                            posSuffix = `<span style="font-size:0.75rem; color:var(--color-text-muted); font-weight:600; margin-left:6px;">(#${nacPos.toLocaleString('pt-BR')}º no país)</span>`;
                        }
                    } else if (scope === "capitais") {
                        // Ranking de Capitais: Inicia em 1ª para a melhor capital
                        posPrefix = `<span style="font-weight:700; color:var(--color-primary-dark); margin-right:4px;">#${idx + 1}ª</span>`;
                        if (nacPos) {
                            posSuffix = `<span style="font-size:0.75rem; color:var(--color-text-muted); font-weight:600; margin-left:6px;">(#${nacPos.toLocaleString('pt-BR')}º no país)</span>`;
                        }
                    } else if (scope === "brasil_piores" || isPiores) {
                        // 100 Piores do Brasil
                        posPrefix = `<span style="font-weight:700; color:#dc2626; margin-right:4px;">#${idx + 1}º menor</span>`;
                        if (nacPos) {
                            posSuffix = `<span style="font-size:0.72rem; color:var(--color-text-muted); font-weight:600; margin-left:6px;">(#${nacPos.toLocaleString('pt-BR')}º no país)</span>`;
                        }
                    } else {
                        // Top 100 Brasil (Melhores)
                        posPrefix = `<span style="font-weight:700; color:var(--color-primary-dark); margin-right:4px;">#${idx + 1}º</span>`;
                    }

                    return `
                        <div class="ranking-row-item" data-ibge="${m.ibge7}" style="display:flex; justify-content:space-between; align-items:center; padding:0.5rem 0.65rem; border:1px solid var(--color-border); border-radius:6px; background:var(--color-surface); cursor:pointer;">
                            <div>
                                ${posPrefix}
                                <strong>${m.nome} (${m.uf})</strong>
                                ${m.eh_capital ? `<span class="badge badge--quality-high" style="margin-left:4px;">Capital</span>` : ""}
                                ${posSuffix}
                                <div style="font-size:0.75rem; color:var(--color-text-subtle); margin-top:1px;">
                                    ${m.populacao ? m.populacao.toLocaleString('pt-BR') + ' hab.' : ''} &bull; 
                                    <span>D1: <strong>${d1}</strong></span> | 
                                    <span>D2: <strong>${d2}</strong></span> | 
                                    <span>D3: <strong>${d3}</strong></span> | 
                                    <span>D5: <strong>${d5}</strong></span> | 
                                    <span>🎗️ Onco: <strong>${typeof m.escore_oncologia === 'number' ? m.escore_oncologia.toFixed(1) : '—'}</strong></span>
                                </div>
                            </div>
                            <span style="background:${getColorForScore(score)}; color:#fff; font-weight:700; font-size:0.8125rem; padding:2px 8px; border-radius:4px; margin-left:8px;">
                                ${scoreFmt}
                            </span>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    };

    // ESCOPO 1: TOP 100 BRASIL (MELHORES NOTAS)
    if (activeRankScope === "brasil") {
        let brasilTop100 = [];
        if (activeRankDim === "nota_geral" && rankingsData.top100_brasil_melhores) {
            brasilTop100 = rankingsData.top100_brasil_melhores;
        } else {
            brasilTop100 = allMun
                .filter(m => typeof m[activeRankDim] === "number")
                .sort((a, b) => (b[activeRankDim] - a[activeRankDim]) || ((b.populacao || 0) - (a.populacao || 0)))
                .slice(0, 100);
        }

        container.innerHTML = `
            <div>
                <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.65rem; color:#1e293b;">
                    🇧🇷 Top 100 Municípios do Brasil (Melhores Notas) — ${activeLabel}
                </h4>
                ${renderMunicipalityList(brasilTop100, false, "brasil")}
            </div>
        `;
    }
    // ESCOPO 1B: 100 PIORES MUNICÍPIOS DO BRASIL (MENORES NOTAS)
    else if (activeRankScope === "brasil_piores") {
        let pioresTop100 = [];
        if (activeRankDim === "nota_geral" && rankingsData.top100_brasil_piores) {
            pioresTop100 = rankingsData.top100_brasil_piores;
        } else {
            pioresTop100 = allMun
                .filter(m => typeof m[activeRankDim] === "number")
                .sort((a, b) => (a[activeRankDim] - b[activeRankDim]) || ((b.populacao || 0) - (a.populacao || 0)))
                .slice(0, 100);
        }

        container.innerHTML = `
            <div>
                <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.65rem; color:#dc2626;">
                    ⚠️ 100 Municípios com Menores Notas do Brasil — ${activeLabel}
                </h4>
                ${renderMunicipalityList(pioresTop100, true, "brasil_piores")}
            </div>
        `;
    }
    // ESCOPO 2: SOMENTE O ESTADO SELECIONADO (TODOS OS MUNICÍPIOS DO ESTADO)
    else if (activeRankScope === "uf") {
        const modalUfSelect = document.getElementById("modal-uf-select");
        const uf = selectedUf || modalUfSelect?.value || "SP";
        if (modalUfSelect && modalUfSelect.value !== uf) {
            modalUfSelect.value = uf;
        }
        const ufInfo = rankingsData.rankings_por_uf?.[uf];
        let ufList = [];
        if (activeRankDim === "nota_geral" && ufInfo?.melhores) {
            ufList = ufInfo.melhores;
        } else {
            ufList = allMun
                .filter(m => m.uf === uf && typeof m[activeRankDim] === "number")
                .sort((a, b) => (b[activeRankDim] - a[activeRankDim]) || ((b.populacao || 0) - (a.populacao || 0)));
        }

        container.innerHTML = `
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.65rem; padding:0.6rem 0.75rem; background:var(--color-bg); border:1px solid var(--color-border); border-radius:6px;">
                    <div>
                        <h4 style="font-size:0.95rem; font-weight:700; margin:0; color:#1e293b;">
                            🏛️ Ranking Estadual Completo — ${ufInfo?.nome_uf || uf} (${uf})
                        </h4>
                        <span style="font-size:0.76rem; color:var(--color-text-muted);">
                            Posição entre Estados: <strong>#${ufInfo?.posicao_uf || '—'}º de 27</strong> &bull;
                            Média UF: <strong>${ufInfo?.media_escore_uf ?? '—'} pts</strong> &bull;
                            Total de Municípios: <strong>${ufList.length}</strong>
                        </span>
                    </div>
                </div>
                ${renderMunicipalityList(ufList, false, "uf")}
            </div>
        `;
    }
    // ESCOPO 3: RANKING DOS 27 ESTADOS + DF (MÉDIA POR ESTADO)
    else if (activeRankScope === "estados") {
        const ufFieldMap = {
            "nota_geral": "media_escore_uf",
            "nota_integrada": "media_integrada_uf",
            "nota_com_urgencia": "media_com_urgencia_uf",
            "d1_nota": "media_d1_uf",
            "d2_nota": "media_d2_uf",
            "d3_nota": "media_d3_uf",
            "d5_nota": "media_d5_uf",
            "escore_oncologia": "media_onco_uf"
        };
        const field = ufFieldMap[activeRankDim] || "media_escore_uf";
        const estados = [...(rankingsData.ranking_estados || [])].sort((a, b) => (b[field] || 0) - (a[field] || 0));

        container.innerHTML = `
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.75rem;">
                    <h4 style="font-size:0.95rem; font-weight:700; margin:0; color:#1e293b;">
                        📊 Ranking das 27 Unidades da Federação — ${activeLabel}
                    </h4>
                    <button id="btn-show-estados-pins" class="btn-ranking-toggle" style="padding:0.3rem 0.65rem; font-size:0.75rem;">
                        📍 Destacar Notas dos 27 Estados no Mapa
                    </button>
                </div>
                <div style="display:flex; flex-direction:column; gap:0.4rem;">
                    ${estados.map((est, idx) => {
                        const score = est[field];
                        return `
                            <div class="ranking-uf-item" data-uf="${est.uf}" style="display:flex; justify-content:space-between; align-items:center; padding:0.55rem 0.7rem; border:1px solid var(--color-border); border-radius:6px; background:var(--color-surface); cursor:pointer;">
                                <div>
                                    <span style="font-weight:700; color:var(--color-primary-dark); margin-right:4px;">#${idx + 1}</span>
                                    <strong>${est.nome_uf} (${est.uf})</strong>
                                    <span style="font-size:0.74rem; color:var(--color-text-subtle); margin-left:4px;">(${est.total_municipios} mun. &bull; ${(est.populacao_uf || 0).toLocaleString('pt-BR')} hab.)</span>
                                    <div style="font-size:0.75rem; color:var(--color-text-subtle); margin-top:2px;">
                                        Média Pond. Pop.: <strong>${est.media_ponderada_uf.toFixed(1)}</strong> &bull;
                                        D1: <strong>${est.media_d1_uf.toFixed(1)}</strong> |
                                        D2: <strong>${est.media_d2_uf.toFixed(1)}</strong> |
                                        D3: <strong>${est.media_d3_uf.toFixed(1)}</strong> |
                                        D5: <strong>${est.media_d5_uf ? est.media_d5_uf.toFixed(1) : '—'}</strong>
                                    </div>
                                    <div style="font-size:0.72rem; color:var(--color-text-muted); margin-top:1px;">
                                        SAMU: <strong>${est.cob_samu_media_uf ?? '—'}%</strong> &bull; UPAs 24h: <strong>${est.total_upas_uf ?? 0}</strong> &bull; Ambulâncias: <strong>${(est.total_usb_uf || 0) + (est.total_usa_uf || 0)}</strong> (USB: ${est.total_usb_uf || 0}, USA: ${est.total_usa_uf || 0})
                                    </div>
                                </div>
                                <span style="background:${getColorForScore(score)}; color:#fff; font-weight:700; font-size:0.85rem; padding:3px 9px; border-radius:4px; margin-left:8px;">
                                    ${score !== null && score !== undefined ? score.toFixed(1) : '—'}
                                </span>
                            </div>
                        `;
                    }).join("")}
                </div>
            </div>
        `;

        const btnPins = container.querySelector("#btn-show-estados-pins");
        if (btnPins) {
            btnPins.addEventListener("click", () => {
                setMarkerMode("estados");
                if (leafletMap) leafletMap.setView([-14.235, -51.925], 4);
                const modalRanking = document.getElementById("rankings-modal");
                if (modalRanking) modalRanking.classList.remove("active");
            });
        }

        container.querySelectorAll(".ranking-uf-item").forEach(row => {
            row.addEventListener("click", () => {
                const uf = row.dataset.uf;
                activeRankScope = "uf";
                const modalUfSelect = document.getElementById("modal-uf-select");
                if (modalUfSelect) modalUfSelect.value = uf;
                syncScopeTabs();
                renderRankingsContent(uf);
            });
        });
        return;
    }
    // ESCOPO 4: RANKING DAS 27 CAPITAIS
    else if (activeRankScope === "capitais") {
        const caps = [...(rankingsData.ranking_capitais || [])].sort((a, b) => {
            const va = typeof a[activeRankDim] === "number" ? a[activeRankDim] : a.escore;
            const vb = typeof b[activeRankDim] === "number" ? b[activeRankDim] : b.escore;
            return vb - va;
        });

        container.innerHTML = `
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.75rem;">
                    <h4 style="font-size:0.95rem; font-weight:700; margin:0; color:#1e293b;">
                        🏙️ Ranking das 27 Capitais Brasileiras — ${activeLabel}
                    </h4>
                    <button id="btn-show-capitais-pins" class="btn-ranking-toggle" style="padding:0.3rem 0.65rem; font-size:0.75rem;">
                        📍 Destacar Notas das 27 Capitais no Mapa
                    </button>
                </div>
                ${renderMunicipalityList(caps, false, "capitais")}
            </div>
        `;

        const btnCapPins = container.querySelector("#btn-show-capitais-pins");
        if (btnCapPins) {
            btnCapPins.addEventListener("click", () => {
                setMarkerMode("capitais");
                if (leafletMap) leafletMap.setView([-14.235, -51.925], 4);
                const modalRanking = document.getElementById("rankings-modal");
                if (modalRanking) modalRanking.classList.remove("active");
            });
        }
    }

    container.querySelectorAll(".ranking-row-item").forEach(item => {
        item.addEventListener("click", () => {
            const ibge7 = item.dataset.ibge;
            const mun = mapaResumoData[ibge7];
            const modalRanking = document.getElementById("rankings-modal");
            if (modalRanking) modalRanking.classList.remove("active");
            if (mun) {
                focusMunicipalityOnMap(ibge7);
                openDrawer(mun, activeIndexMode);
            }
        });
    });
}
