/**
 * site/assets/js/app.js
 * 
 * Controlador Principal do Front-end Estático (ES Modules)
 * - Carrega meta_build.json gerado pelo pipeline
 * - Gerencia navegação por abas (Mapa, Metodologia, Fontes, Downloads)
 * - Inicializa o Mapa Leaflet, a Gaveta Municipal e as Vistas Dinâmicas
 */

import { initMap } from "./map.js?v=0.4.0";
import { initDrawer } from "./drawer_municipio.js?v=0.4.0";
import { renderMethodologyView } from "./methodology_view.js?v=0.4.0";
import { renderSourcesView } from "./sources_view.js?v=0.4.0";
import { renderDownloadsView } from "./downloads_view.js?v=0.4.0";

let metaBuild = null;

async function fetchMetaBuild() {
    const candidatePaths = [
        "data/releases/latest/meta_build.json",
        "./data/releases/latest/meta_build.json",
        "../data/releases/latest/meta_build.json",
        "/data/releases/latest/meta_build.json"
    ];

    for (const path of candidatePaths) {
        try {
            const res = await fetch(path);
            if (res.ok) {
                return await res.json();
            }
        } catch (e) {
            // Continua para o próximo
        }
    }
    console.warn("[app.js] meta_build.json não pôde ser carregado diretamente.");
    return null;
}

function setupNavigation() {
    const tabs = document.querySelectorAll(".nav-tab");
    const panels = document.querySelectorAll(".view-panel");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const targetView = tab.dataset.view;

            tabs.forEach(t => t.classList.remove("active"));
            panels.forEach(p => p.classList.remove("active"));

            tab.classList.add("active");
            const activePanel = document.getElementById(`view-${targetView}`);
            if (activePanel) {
                activePanel.classList.add("active");
            }

            // Atualização de URL hash sem reload
            window.location.hash = targetView;
        });
    });

    // Leitura do hash inicial
    const initialHash = window.location.hash.replace("#", "");
    if (initialHash) {
        const matchingTab = document.querySelector(`.nav-tab[data-view="${initialHash}"]`);
        if (matchingTab) {
            matchingTab.click();
        }
    }
}

async function init() {
    console.log("[app.js] Iniciando aplicação Índice de Saúde Municipal...");

    // 1. Configura a navegação por abas imediatamente
    setupNavigation();

    // 2. Carrega metadados de build do pipeline
    try {
        metaBuild = await fetchMetaBuild();

        // Atualiza badges de versão no cabeçalho
        if (metaBuild?.versao_metodologia) {
            const versionBadges = document.querySelectorAll(".version-display");
            versionBadges.forEach(badge => {
                badge.textContent = metaBuild.versao_metodologia;
            });
        }

        // Inicializa a gaveta municipal
        initDrawer(metaBuild);

        // Renderiza as vistas dinâmicas baseadas no meta_build.json
        renderMethodologyView(metaBuild);
        renderSourcesView(metaBuild);
        renderDownloadsView(metaBuild);
    } catch (e) {
        console.warn("[app.js] Erro ao carregar metadados complementares:", e);
    }

    // 3. Inicializa o mapa interativo
    try {
        await initMap(metaBuild);
    } catch (e) {
        console.error("[app.js] Erro ao inicializar o mapa interativo:", e);
    }

    console.log("[app.js] Aplicação inicializada com sucesso.");
}

// Inicialização resiliente ao ciclo de vida de ES Modules
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        init().catch(err => console.error("[app.js] Erro crítico:", err));
    });
} else {
    init().catch(err => console.error("[app.js] Erro crítico:", err));
}
