/**
 * site/assets/js/map.js
 * 
 * Mapa Coroplético e Controle de Visualização Territorial (Leaflet)
 * - Carrega data/releases/latest/mapa_resumo.json (5.570 municípios)
 * - Suporte a camadas: Nota Geral, D1, D2, D3
 * - Tratamento visual estrito para status 'sem_classificacao'
 * - Busca com debounce para os 5.570 municípios e filtros por UF e Região
 * - Disparo da Ficha Lateral (openDrawer)
 */

import { openDrawer } from "./drawer_municipio.js";

let leafletMap = null;
let mapaResumoData = {};
let rankingsData = {};
let activeLayerKey = "nota_geral"; // 'nota_geral' | 'd1_nota' | 'd2_nota' | 'd3_nota'
let geoJsonLayer = null;

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

    // 1. Inicializa o objeto Leaflet centrado no Brasil com aceleração via Canvas
    leafletMap = L.map("leaflet-map", {
        center: [-14.235, -51.925],
        zoom: 4,
        minZoom: 3,
        maxZoom: 18,
        preferCanvas: true
    });

    // 2. Camadas de Mapa Base (Google Maps e alternativas sem restrição de API Key)
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

    // Google Maps Padrão ativado por padrão
    googlePadrao.addTo(leafletMap);

    // Controle de seleção de mapa base estilo Google Maps
    const baseMaps = {
        "Google Maps (Padrão)": googlePadrao,
        "Google Maps (Relevo)": googleTerreno,
        "Google Maps (Satélite)": googleHibrido,
        "OpenStreetMap": openStreetMap
    };
    L.control.layers(baseMaps, null, { position: "topright" }).addTo(leafletMap);

    // 3. Carrega o payload de dados municipais e rankings
    await loadMapaResumo();
    await loadRankings();

    // 4. Configura controles de busca, filtros, seletor de camada e ranking
    setupLayerSelector();
    setupSearchAndFilters();
    setupRankingsModal();

    // 5. Tentativa de carregamento da malha geográfica TopoJSON/GeoJSON
    await loadGeoBoundary();
}

async function loadRankings() {
    try {
        const response = await fetch("data/releases/latest/rankings_resumo.json");
        if (response.ok) {
            rankingsData = await response.json();
            console.log("[map.js] rankings_resumo.json carregado com sucesso.");
        }
    } catch (e) {
        try {
            const fallbackRes = await fetch("../data/releases/latest/rankings_resumo.json");
            rankingsData = await fallbackRes.json();
        } catch (e2) {
            console.warn("[map.js] Rankings não disponíveis no momento.");
        }
    }
}

async function loadMapaResumo() {
    try {
        const response = await fetch("data/releases/latest/mapa_resumo.json");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} ao carregar mapa_resumo.json`);
        }
        mapaResumoData = await response.json();
        console.log(`[map.js] ${Object.keys(mapaResumoData).length} municípios carregados.`);
    } catch (err) {
        console.warn("[map.js] Erro ao carregar mapa_resumo.json, tentando caminho alternativo:", err);
        try {
            const fallbackRes = await fetch("../data/releases/latest/mapa_resumo.json");
            mapaResumoData = await fallbackRes.json();
        } catch (e2) {
            console.error("[map.js] Falha crítica ao obter mapa_resumo.json:", e2);
        }
    }
}

async function loadGeoBoundary() {
    const geoPaths = [
        "assets/geo/br_municipios.json",
        "site/assets/geo/br_municipios.json",
        "site/assets/geo/br_municipios.topojson",
        "assets/geo/br_municipios.topojson",
        "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-100-mun.json"
    ];

    for (const path of geoPaths) {
        try {
            const res = await fetch(path);
            if (res.ok) {
                const geoData = await res.json();
                console.log(`[map.js] Malha geográfica carregada com sucesso a partir de ${path}`);
                renderGeoJson(geoData);
                return;
            }
        } catch (e) {
            // Continua para o próximo
        }
    }

    console.log("[map.js] Malha TopoJSON local ausente. Modo de busca vetorial e seleção direta ativo.");
}

function renderGeoJson(geoData) {
    if (geoJsonLayer) {
        leafletMap.removeLayer(geoJsonLayer);
    }

    geoJsonLayer = L.geoJSON(geoData, {
        style: styleFeature,
        onEachFeature: (feature, layer) => {
            const ibge = feature.properties?.id || feature.properties?.codarea || feature.properties?.ibge7;
            const mun = mapaResumoData[ibge] || { nome: feature.properties?.name || "Município", ibge7: ibge };
            const popFmt = mun.populacao ? mun.populacao.toLocaleString("pt-BR") + " hab." : "População em validação";
            const escoreFmt = mun.nota_geral !== null && mun.nota_geral !== undefined ? mun.nota_geral.toFixed(1) : null;
            const tmiFmt = mun.indicadores?.D1.1?.valor !== null && mun.indicadores?.D1.1?.valor !== undefined ? mun.indicadores.D1.1.valor.toFixed(1) + " por 1.000 NV" : null;
            const corNota = getColorForScore(mun.nota_geral);

            let statusBlock = "";
            if (escoreFmt) {
                statusBlock = `
                    <div style="margin: 4px 0 6px 0;">
                        <span style="background:${corNota}; color:#ffffff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.85rem; display:inline-block;">
                            Nota D1.1: ${escoreFmt} / 100
                        </span>
                    </div>
                    <span style="color:#1e293b;">📉 Mortalidade Infantil: <strong>${tmiFmt}</strong></span><br>
                    <span style="color:#475569;">🏆 Ranking Nacional: <strong>#${mun.posicao_nacional}</strong> de 5.570</span><br>
                    <span style="color:#475569;">🥇 Ranking Estadual (${mun.uf}): <strong>#${mun.posicao_estadual}º</strong></span><br>
                `;
            } else {
                statusBlock = `<span style="color:#d97706; font-weight:700;">Status: Sem Classificação (Fase 0)</span><br>`;
            }
            
            layer.bindTooltip(`
                <div style="font-size:0.8125rem; line-height:1.45; min-width:200px; padding:2px;">
                    <strong style="font-size:1rem; color:#0f172a;">${mun.nome} (${mun.uf || ''})</strong><br>
                    <span style="color:#475569;">👥 População: <strong>${popFmt}</strong></span><br>
                    ${statusBlock}
                    <span style="color:#0284c7; font-size:0.75rem; font-weight:600; display:block; margin-top:4px;">👉 Clique para abrir a ficha completa</span>
                </div>
            `, {
                sticky: true
            });

            layer.on({
                click: () => openDrawer(mun),
                mouseover: (e) => {
                    const l = e.target;
                    l.setStyle({ weight: 2.5, color: "#0284c7", fillOpacity: 0.85 });
                },
                mouseout: (e) => {
                    geoJsonLayer.resetStyle(e.target);
                }
            });
        }
    }).addTo(leafletMap);
}

function styleFeature(feature) {
    const ibge = feature.properties?.id || feature.properties?.codarea || feature.properties?.ibge7;
    const mun = mapaResumoData[ibge];

    // Regra 3 e 4: Sem classificação recebe padrão visual cinza neutro
    if (!mun || mun.status === "sem_classificacao" || mun[activeLayerKey] === null) {
        return {
            fillColor: "#94a3b8",
            weight: 0.6,
            opacity: 0.9,
            color: "#475569",
            dashArray: "2, 2",
            fillOpacity: 0.35
        };
    }

    const val = mun[activeLayerKey];
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

function setupLayerSelector() {
    const layerButtons = document.querySelectorAll(".layer-btn");
    layerButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            layerButtons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            activeLayerKey = btn.dataset.layer;
            console.log(`[map.js] Camada ativa alterada para: ${activeLayerKey}`);
            if (geoJsonLayer) {
                geoJsonLayer.setStyle(styleFeature);
            }
        });
    });
}

function setupSearchAndFilters() {
    const searchInput = document.getElementById("search-municipio-input");
    const dropdown = document.getElementById("search-results-dropdown");
    const ufFilter = document.getElementById("uf-filter");

    // Popula o select de UFs e trata zoom automático
    if (ufFilter) {
        const ufs = [...new Set(Object.values(mapaResumoData).map(m => m.uf))].filter(Boolean).sort();
        ufs.forEach(uf => {
            const opt = document.createElement("option");
            opt.value = uf;
            opt.textContent = uf;
            ufFilter.appendChild(opt);
        });

        ufFilter.addEventListener("change", () => {
            const selectedUf = ufFilter.value;
            if (selectedUf) {
                console.log(`[map.js] Filtro por UF selecionado: ${selectedUf}`);
                const centerCfg = UF_CENTERS[selectedUf];
                if (centerCfg && leafletMap) {
                    leafletMap.setView([centerCfg[0], centerCfg[1]], centerCfg[2]);
                }
                // Atualiza painel de rankings se aberto
                renderRankingsContent(selectedUf);
            }
        });
    }

    if (!searchInput || !dropdown) return;

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
                    m.nome.toLowerCase().includes(query) ||
                    m.ibge7.includes(query) ||
                    m.ibge6.includes(query)
                )
                .slice(0, 15);

            if (results.length === 0) {
                dropdown.innerHTML = `<div class="search-item" style="color: var(--color-text-subtle);">Nenhum município encontrado</div>`;
            } else {
                dropdown.innerHTML = results.map(m => `
                    <div class="search-item" data-ibge="${m.ibge7}">
                        <strong>${m.nome} (${m.uf})</strong>
                        <span style="font-size: 0.75rem; color: var(--color-text-subtle);">IBGE: ${m.ibge7}</span>
                    </div>
                `).join("");

                dropdown.querySelectorAll(".search-item").forEach(item => {
                    item.addEventListener("click", () => {
                        const ibge7 = item.dataset.ibge;
                        const mun = mapaResumoData[ibge7];
                        dropdown.classList.remove("visible");
                        searchInput.value = `${mun.nome} (${mun.uf})`;
                        openDrawer(mun);
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

function setupRankingsModal() {
    const btnRanking = document.getElementById("btn-toggle-ranking");
    const modalRanking = document.getElementById("rankings-modal");
    const btnCloseRank = document.getElementById("btn-close-ranking");

    if (btnRanking && modalRanking) {
        btnRanking.addEventListener("click", () => {
            const ufFilter = document.getElementById("uf-filter");
            const activeUf = ufFilter ? ufFilter.value : "";
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

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modalRanking && modalRanking.classList.contains("active")) {
            modalRanking.classList.remove("active");
        }
    });
}

function renderRankingsContent(selectedUf = "") {
    const container = document.getElementById("rankings-modal-body");
    if (!container || !rankingsData || !rankingsData.top10_brasil_melhores) {
        if (container) container.innerHTML = `<p style="color:var(--color-text-subtle);">Carregando rankings oficiais...</p>`;
        return;
    }

    const ufInfo = selectedUf ? rankingsData.rankings_por_uf?.[selectedUf] : null;
    const ufTitle = selectedUf ? `Top 10 — ${selectedUf} (Média Estadual: ${ufInfo?.media_escore_uf || '—'} pts)` : "Selecione um Estado no filtro de UF para ver o ranking estadual";

    const renderList = (items) => {
        if (!items || items.length === 0) return "<p style='color:var(--color-text-subtle);'>Nenhum município listado.</p>";
        return `
            <div style="display:flex; flex-direction:column; gap:0.4rem;">
                ${items.map((m, idx) => `
                    <div class="ranking-row-item" data-ibge="${m.ibge7}" style="display:flex; justify-content:space-between; align-items:center; padding:0.5rem 0.65rem; border:1px solid var(--color-border); border-radius:6px; background:var(--color-surface); cursor:pointer;">
                        <div>
                            <span style="font-weight:700; color:var(--color-primary-dark); margin-right:4px;">#${idx + 1}</span>
                            <strong>${m.nome} (${m.uf})</strong>
                            <div style="font-size:0.75rem; color:var(--color-text-subtle);">${m.populacao ? m.populacao.toLocaleString('pt-BR') + ' hab.' : ''} | TMI: ${m.tmi_bayes.toFixed(1)}/mil NV</div>
                        </div>
                        <span style="background:${getColorForScore(m.escore)}; color:#fff; font-weight:700; font-size:0.8125rem; padding:2px 8px; border-radius:4px;">
                            ${m.escore.toFixed(1)}
                        </span>
                    </div>
                `).join("")}
            </div>
        `;
    };

    container.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:1.25rem;">
            <div>
                <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.5rem; color:#1e293b;">
                    🇧🇷 Top 10 Brasil — Menor Mortalidade Infantil (D1.1)
                </h4>
                ${renderList(rankingsData.top10_brasil_melhores)}
            </div>

            <div>
                <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.5rem; color:#1e293b;">
                    🏛️ ${ufTitle}
                </h4>
                ${selectedUf ? renderList(ufInfo?.melhores) : `<p style="font-size:0.8125rem; color:var(--color-text-subtle);">Escolha um estado no topo da página (ex.: MG, SP, BA) para listar os líderes estaduais.</p>`}
            </div>
        </div>
    `;

    // Clique em qualquer item do ranking voa para o município e abre a ficha
    container.querySelectorAll(".ranking-row-item").forEach(item => {
        item.addEventListener("click", () => {
            const ibge7 = item.dataset.ibge;
            const mun = mapaResumoData[ibge7];
            const modalRanking = document.getElementById("rankings-modal");
            if (modalRanking) modalRanking.classList.remove("active");
            if (mun) {
                openDrawer(mun);
            }
        });
    });
}
