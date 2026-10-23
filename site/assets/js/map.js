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
let activeLayerKey = "nota_geral"; // 'nota_geral' | 'd1_nota' | 'd2_nota' | 'd3_nota'
let geoJsonLayer = null;

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

    // 3. Carrega o payload de dados municipais
    await loadMapaResumo();

    // 4. Configura controles de busca, filtros e seletor de camada
    setupLayerSelector();
    setupSearchAndFilters();

    // 5. Tentativa de carregamento da malha geográfica TopoJSON/GeoJSON
    await loadGeoBoundary();
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
            const popFmt = mun.populacao ? mun.populacao.toLocaleString("pt-BR") + " hab. (Censo 2022)" : "População em validação";
            const porteFmt = mun.porte || "—";
            
            layer.bindTooltip(`
                <div style="font-size:0.8125rem; line-height:1.4; padding:2px;">
                    <strong style="font-size:0.95rem; color:#0f172a;">${mun.nome} (${mun.uf || ''})</strong><br>
                    <span style="color:#334155;">👥 <strong>${popFmt}</strong></span><br>
                    <span style="color:#475569;">🏷️ Porte: ${porteFmt}</span><br>
                    <span style="color:#d97706; font-weight:700;">Status: Sem Classificação (Fase 0)</span><br>
                    <span style="color:#0284c7; font-size:0.75rem; font-weight:600;">👉 Clique para abrir a ficha técnica</span>
                </div>
            `, {
                sticky: true
            });

            layer.on({
                click: () => openDrawer(mun),
                mouseover: (e) => {
                    const l = e.target;
                    l.setStyle({ weight: 2.5, color: "#0284c7", fillOpacity: 0.6 });
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
        opacity: 1,
        color: "#ffffff",
        fillOpacity: 0.8
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

    // Popula o select de UFs
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
