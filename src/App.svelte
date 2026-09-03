<script>
  import { onMount } from 'svelte';
  import Chart from 'chart.js/auto';

  // URL-ul backend-ului deployed pe Render
  const API_BASE_URL = 'https://gestiune-stocuri-api.onrender.com';

  let produse = [];
  let searchQuery = '';
  let selectedCategory = 'Toate';
  let stockFilter = 'Toate';
  let loading = true;

  let sortColumn = 'produs_nume';
  let sortDirection = 'asc';

  let showAddModal = false;
  let showEditModal = false;
  let showDeleteModal = false;

  let selectedItemToEdit = null;
  let selectedItemToDelete = null;
  let editStocValue = 0;

  let newProdus = {
    categorie_id: 1,
    nume: '',
    descriere: '',
    stoc_minim_alerta: 2,
    sku: '',
    culoare: '',
    material: '',
    dimensiune: '',
    pret_achizitie: 0,
    pret_vanzare: 0,
    stoc_curent: 0
  };

  let stats = {
    valoare_achizitie: 0,
    valoare_vanzare: 0,
    profit_potential: 0,
    stoc_critic: 0,
    stoc_categorii: [],
    top_produse: []
  };

  let chartCategoriiInstance = null;
  let chartTopInstance = null;
  let canvasCategorii;
  let canvasTop;

  async function fetchProduse() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/produse`);
      produse = await res.json();
    } catch (e) {
      console.error("Eroare la incarcarea produselor:", e);
    }
  }

  async function fetchStats() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/dashboard/stats`);
      stats = await res.json();
      renderCharts();
    } catch (e) {
      console.error("Eroare la incarcarea datelor de dashboard:", e);
    }
  }

  function toggleSort(column) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = column;
      sortDirection = 'asc';
    }
  }

  function openEditModal(item) {
    selectedItemToEdit = item;
    editStocValue = item.stoc_curent;
    showEditModal = true;
  }

  function openDeleteModal(item) {
    selectedItemToDelete = item;
    showDeleteModal = true;
  }

  async function submitEditStoc() {
    if (!selectedItemToEdit) return;
    const val = parseInt(editStocValue, 10);
    if (isNaN(val) || val < 0) return;

    await fetch(`${API_BASE_URL}/api/variante/${selectedItemToEdit.varianta_id}/stoc`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stoc_curent: val })
    });

    showEditModal = false;
    refreshAll();
  }

  async function confirmDeleteProduct() {
    if (!selectedItemToDelete) return;

    try {
      const res = await fetch(`${API_BASE_URL}/api/variante/${selectedItemToDelete.varianta_id}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        showDeleteModal = false;
        selectedItemToDelete = null;
        refreshAll();
      } else {
        alert("Eroare la ștergerea produsului!");
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function handleAddProduct() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/produse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProdus)
      });

      if (res.ok) {
        showAddModal = false;
        newProdus = {
          categorie_id: 1, nume: '', descriere: '', stoc_minim_alerta: 2,
          sku: '', culoare: '', material: '', dimensiune: '',
          pret_achizitie: 0, pret_vanzare: 0, stoc_curent: 0
        };
        refreshAll();
      } else {
        alert("A apărut o eroare la adăugarea produsului!");
      }
    } catch (e) {
      console.error(e);
    }
  }

  function renderCharts() {
    if (chartCategoriiInstance) chartCategoriiInstance.destroy();
    if (chartTopInstance) chartTopInstance.destroy();

    if (canvasCategorii && stats.stoc_categorii) {
      chartCategoriiInstance = new Chart(canvasCategorii, {
        type: 'doughnut',
        data: {
          labels: stats.stoc_categorii.map(c => c.categorie),
          datasets: [{
            data: stats.stoc_categorii.map(c => c.stoc),
            backgroundColor: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }

    if (canvasTop && stats.top_produse) {
      chartTopInstance = new Chart(canvasTop, {
        type: 'bar',
        data: {
          labels: stats.top_produse.map(p => p.produs),
          datasets: [{
            label: 'Bucăți în stoc',
            data: stats.top_produse.map(p => p.stoc),
            backgroundColor: '#6366F1'
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });
    }
  }

  function descarcaPDF() {
    window.open(`${API_BASE_URL}/api/raport/pdf`, '_blank');
  }

  function descarcaCSV() {
    window.open(`${API_BASE_URL}/api/raport/csv`, '_blank');
  }

  function refreshAll() {
    loading = true;
    Promise.all([fetchProduse(), fetchStats()]).then(() => {
      loading = false;
    });
  }

  onMount(() => {
    refreshAll();
  });

  $: categoriiUnice = ['Toate', ...new Set(produse.map(p => p.categorie_nume))];

  $: produseFiltrate = produse
    .filter(p => {
      const matchesSearch = (p.produs_nume || '').toLowerCase().includes(searchQuery.toLowerCase()) || 
                            (p.sku || '').toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = selectedCategory === 'Toate' || p.categorie_nume === selectedCategory;
      
      let matchesStock = true;
      if (stockFilter === 'InStoc') matchesStock = p.stoc_curent > 0;
      if (stockFilter === 'FaraStoc') matchesStock = p.stoc_curent === 0;

      return matchesSearch && matchesCategory && matchesStock;
    })
    .sort((a, b) => {
      let valA = a[sortColumn];
      let valB = b[sortColumn];

      if (typeof valA === 'string') {
        valA = valA.toLowerCase();
        valB = valB.toLowerCase();
      }

      if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
      if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
</script>

<main class="container">
  <header>
    <div>
      <h1>Gestiune Stocuri Mobilă</h1>
      <p class="subtitle">Panou de control & gestiune stocuri</p>
    </div>
    <div class="header-buttons">
      <button on:click={() => showAddModal = true} class="btn btn-add">+ Adaugă Produs</button>
      <button on:click={descarcaCSV} class="btn btn-csv">📊 Export CSV</button>
      <button on:click={descarcaPDF} class="btn btn-pdf">📄 Raport PDF</button>
      <button on:click={refreshAll} class="btn btn-refresh">↻ Actualizează</button>
    </div>
  </header>

  <section class="kpi-grid">
    <div class="card">
      <span class="card-title">Valoare Achiziție</span>
      <p class="valoare">{(stats.valoare_achizitie || 0).toLocaleString()} lei</p>
    </div>
    <div class="card">
      <span class="card-title">Valoare Vânzare</span>
      <p class="valoare">{(stats.valoare_vanzare || 0).toLocaleString()} lei</p>
    </div>
    <div class="card success">
      <span class="card-title">Profit Potențial</span>
      <p class="valoare">{(stats.profit_potential || 0).toLocaleString()} lei</p>
    </div>
    <div class="card alert">
      <span class="card-title">Stoc Critic</span>
      <p class="valoare">{stats.stoc_critic || 0} produse</p>
    </div>
  </section>

  <section class="charts-grid">
    <div class="chart-box">
      <h3>Stoc pe Categorii</h3>
      <div class="chart-wrapper">
        <canvas bind:this={canvasCategorii}></canvas>
      </div>
    </div>
    <div class="chart-box">
      <h3>Top Produse în Stoc</h3>
      <div class="chart-wrapper">
        <canvas bind:this={canvasTop}></canvas>
      </div>
    </div>
  </section>

  <section class="controls">
    <input 
      type="text" 
      placeholder="Căutare după nume produs sau SKU..." 
      bind:value={searchQuery} 
      class="search-input"
    />
    
    <select bind:value={selectedCategory} class="select-category">
      {#each categoriiUnice as cat}
        <option value={cat}>{cat}</option>
      {/each}
    </select>

    <div class="toggle-group">
      <button class="toggle-btn {stockFilter === 'Toate' ? 'active' : ''}" on:click={() => stockFilter = 'Toate'}>Toate</button>
      <button class="toggle-btn {stockFilter === 'InStoc' ? 'active' : ''}" on:click={() => stockFilter = 'InStoc'}>✓ În Stoc</button>
      <button class="toggle-btn {stockFilter === 'FaraStoc' ? 'active' : ''}" on:click={() => stockFilter = 'FaraStoc'}>✕ Fără Stoc</button>
    </div>
  </section>

  {#if loading}
    <p class="loading">Se încarcă datele...</p>
  {:else}
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th class="sortable" on:click={() => toggleSort('produs_nume')}>
              PRODUS {sortColumn === 'produs_nume' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th class="sortable" on:click={() => toggleSort('sku')}>
              SKU {sortColumn === 'sku' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th>DETALII</th>
            <th class="sortable" on:click={() => toggleSort('pret_vanzare')}>
              PREȚ {sortColumn === 'pret_vanzare' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th class="sortable" on:click={() => toggleSort('stoc_curent')}>
              STOC CURENT {sortColumn === 'stoc_curent' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th>STATUS</th>
            <th>ACȚIUNI</th>
          </tr>
        </thead>
        <tbody>
          {#each produseFiltrate as item}
            <tr>
              <td class="font-bold">{item.produs_nume}</td>
              <td class="sku-cell">{item.sku}</td>
              <td>{item.culoare ? item.culoare : ''} {item.material ? '- ' + item.material : ''}</td>
              <td class="font-bold">{item.pret_vanzare} lei</td>
              <td class="font-bold">{item.stoc_curent} buc.</td>
              <td>
                {#if item.stoc_curent === 0}
                  <span class="badge badge-danger">Out of Stock</span>
                {:else if item.stoc_curent <= item.stoc_minim_alerta}
                  <span class="badge badge-alert">⚠️ Stoc Scăzut</span>
                {:else}
                  <span class="badge badge-success">✓ În Stoc</span>
                {/if}
              </td>
              <td>
                <div class="actions-cell">
                  <button class="btn-sm" on:click={() => openEditModal(item)}>✏ Edit Stoc</button>
                  <button class="btn-sm btn-delete-sm" on:click={() => openDeleteModal(item)}>🗑 Șterge</button>
                </div>
              </td>
            </tr>
          {/each}
          {#if produseFiltrate.length === 0}
            <tr>
              <td colspan="7" class="empty-state">Nu există produse pentru filtrul selectat.</td>
            </tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</main>

{#if showAddModal}
  <div class="modal-backdrop">
    <div class="modal">
      <h2>Adaugă Produs Nou</h2>
      <form on:submit|preventDefault={handleAddProduct}>
        <div class="form-grid">
          <div>
            <label>Nume Produs</label>
            <input type="text" bind:value={newProdus.nume} required />
          </div>
          <div>
            <label>Categorie</label>
            <select bind:value={newProdus.categorie_id}>
              <option value={1}>Canapele</option>
              <option value={2}>Fotolii & Taburete</option>
              <option value={3}>Accesorii & Perne</option>
            </select>
          </div>
          <div>
            <label>SKU</label>
            <input type="text" bind:value={newProdus.sku} required />
          </div>
          <div>
            <label>Culoare</label>
            <input type="text" bind:value={newProdus.culoare} />
          </div>
          <div>
            <label>Material</label>
            <input type="text" bind:value={newProdus.material} />
          </div>
          <div>
            <label>Dimensiune</label>
            <input type="text" bind:value={newProdus.dimensiune} />
          </div>
          <div>
            <label>Preț Achiziție (lei)</label>
            <input type="number" step="0.01" bind:value={newProdus.pret_achizitie} required />
          </div>
          <div>
            <label>Preț Vânzare (lei)</label>
            <input type="number" step="0.01" bind:value={newProdus.pret_vanzare} required />
          </div>
          <div>
            <label>Stoc Inițial</label>
            <input type="number" bind:value={newProdus.stoc_curent} required />
          </div>
          <div>
            <label>Stoc Min. Alertă</label>
            <input type="number" bind:value={newProdus.stoc_minim_alerta} required />
          </div>
        </div>

        <div class="modal-actions">
          <button type="button" class="btn-cancel" on:click={() => showAddModal = false}>Anulează</button>
          <button type="submit" class="btn btn-add">Salvează Produs</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if showEditModal}
  <div class="modal-backdrop">
    <div class="modal modal-small">
      <h2>Modificare Stoc</h2>
      <p><strong>{selectedItemToEdit?.produs_nume}</strong> ({selectedItemToEdit?.sku})</p>
      
      <div style="margin: 20px 0;">
        <label style="font-size: 0.85rem; font-weight: 600; color: #475569;">Noul Stoc:</label>
        <input type="number" min="0" bind:value={editStocValue} style="width: 100%; padding: 10px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 6px;" />
      </div>

      <div class="modal-actions">
        <button type="button" class="btn-cancel" on:click={() => showEditModal = false}>Anulează</button>
        <button type="button" class="btn btn-refresh" on:click={submitEditStoc}>Actualizează</button>
      </div>
    </div>
  </div>
{/if}

{#if showDeleteModal}
  <div class="modal-backdrop">
    <div class="modal modal-small">
      <h2 style="color: #ef4444;">Ștergere Produs</h2>
      <p>Ești sigur că vrei să ștergi produsul <strong>{selectedItemToDelete?.produs_nume}</strong> (SKU: {selectedItemToDelete?.sku})?</p>
      <p style="font-size: 0.85rem; color: #64748b;">Această acțiune este ireversibilă!</p>

      <div class="modal-actions">
        <button type="button" class="btn-cancel" on:click={() => showDeleteModal = false}>Anulează</button>
        <button type="button" class="btn btn-pdf" on:click={confirmDeleteProduct}>Da, Șterge</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .container { max-width: 1400px; margin: 0 auto; padding: 24px; font-family: system-ui, -apple-system, sans-serif; color: #0f172a; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px; }
  h1 { margin: 0; font-size: 1.875rem; font-weight: 700; color: #0f172a; }
  .subtitle { margin: 4px 0 0 0; color: #64748b; font-size: 0.95rem; }
  .header-buttons { display: flex; gap: 10px; flex-wrap: wrap; }

  .btn { border: none; padding: 10px 16px; border-radius: 6px; font-weight: 600; font-size: 0.875rem; cursor: pointer; transition: background 0.2s, opacity 0.2s; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
  .btn:hover { opacity: 0.9; }
  .btn-add { background: #10b981; color: white; }
  .btn-csv { background: #059669; color: white; }
  .btn-pdf { background: #dc2626; color: white; }
  .btn-refresh { background: #2563eb; color: white; }

  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  .card-title { font-size: 0.8rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .valoare { font-size: 1.6rem; font-weight: 700; margin: 8px 0 0 0; color: #1e293b; }
  .card.success .valoare { color: #10b981; }
  .card.alert .valoare { color: #ef4444; }

  .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 28px; }
  .chart-box { background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  .chart-box h3 { margin-top: 0; margin-bottom: 16px; font-size: 1.05rem; color: #334155; }
  .chart-wrapper { position: relative; height: 260px; }

  .controls { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
  .search-input { flex: 2; min-width: 260px; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem; }
  .select-category { flex: 1; min-width: 160px; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem; background: white; cursor: pointer; }

  .toggle-group { display: inline-flex; border: 1px solid #cbd5e1; border-radius: 6px; overflow: hidden; background: white; height: 40px; }
  .toggle-btn { background: white; border: none; padding: 0 16px; font-size: 0.875rem; font-weight: 500; cursor: pointer; border-right: 1px solid #cbd5e1; color: #475569; display: flex; align-items: center; white-space: nowrap; }
  .toggle-btn:last-child { border-right: none; }
  .toggle-btn.active { background: #2563eb; color: white; font-weight: 600; }

  .table-container { background: white; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }
  th { background: #f8fafc; padding: 14px 16px; border-bottom: 1px solid #e2e8f0; color: #475569; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; white-space: nowrap; }
  th.sortable { cursor: pointer; user-select: none; }
  th.sortable:hover { background: #f1f5f9; color: #0f172a; }
  
  td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
  .font-bold { font-weight: 600; color: #0f172a; }
  .sku-cell { font-family: monospace; color: #3b82f6; font-size: 0.85rem; font-weight: 600; white-space: nowrap; }

  .badge { display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; white-space: nowrap; }
  .badge-success { background: #d1fae5; color: #047857; }
  .badge-alert { background: #fef3c7; color: #b45309; }
  .badge-danger { background: #fee2e2; color: #b91c1c; }

  .actions-cell { display: flex; gap: 6px; }
  .btn-sm { background: #f8fafc; border: 1px solid #cbd5e1; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 500; color: #334155; white-space: nowrap; transition: all 0.15s ease; }
  .btn-sm:hover { background: #e2e8f0; border-color: #94a3b8; color: #0f172a; }
  .btn-delete-sm { color: #dc2626; border-color: #fca5a5; background: #fff5f5; }
  .btn-delete-sm:hover { background: #fee2e2; border-color: #ef4444; color: #991b1b; }

  .loading { text-align: center; color: #64748b; padding: 40px; }
  .empty-state { text-align: center; padding: 40px; color: #94a3b8; }

  .modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(2px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
  .modal { background: white; padding: 28px; border-radius: 12px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
  .modal-small { max-width: 420px; }
  .modal h2 { margin-top: 0; margin-bottom: 16px; font-size: 1.3rem; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .form-grid label { font-size: 0.8rem; font-weight: 600; color: #475569; display: block; margin-bottom: 4px; }
  .form-grid input, .form-grid select { width: 100%; padding: 9px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 0.9rem; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
  .btn-cancel { background: #f1f5f9; border: 1px solid #cbd5e1; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; color: #475569; }
  .btn-cancel:hover { background: #e2e8f0; }
</style>
