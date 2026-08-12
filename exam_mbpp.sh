#!/usr/bin/env bash
#
# run_mbpp.sh — boucle dump / solve / validate sur MBPP + summary final
#
# Pour chaque itération :
#   1) dump    : uv run python3 -m moulinette dump mbpp --output ../cache/mbpp_task.json   (dans moulinette/)
#   2) solve   : uv run python  -m agent_mbpp --task-file cache/mbpp_task.json \
#                                             --output    cache/mbpp_solution.json          (à la racine)
#   3) validate: uv run python3 -m moulinette validate mbpp \
#                     ../cache/mbpp_task.json ../cache/mbpp_solution.json                    (dans moulinette/)
#
# Usage:
#   ./run_mbpp.sh [N]
#       N = nombre d'itérations (défaut: 10)
#
# À placer à la racine du projet (à côté de moulinette/ et cache/).
# Sinon: AGENTSMITH_ROOT=/chemin/vers/AgentSmith ./run_mbpp.sh 10

set -uo pipefail # PAS de -e : on veut gérer les échecs nous-mêmes et continuer la boucle

# ---------- config ----------
N="${1:-10}"

ROOT="${AGENTSMITH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
MOULINETTE_DIR="$ROOT/moulinette"
CACHE_DIR="$ROOT/cache"
LOG_DIR="$CACHE_DIR/logs"

# chemins relatifs à la racine (pour l'agent)
TASK_FILE_REL="cache/mbpp_task.json"
SOLUTION_FILE_REL="cache/mbpp_solution.json"
# chemins relatifs à moulinette/ (pour dump & validate)
TASK_FILE_MOUL="../cache/mbpp_task.json"
SOLUTION_FILE_MOUL="../cache/mbpp_solution.json"

# ---------- couleurs (désactivées si pas un terminal) ----------
if [ -t 1 ]; then
	RED=$'\033[31m'
	GRN=$'\033[32m'
	YLW=$'\033[33m'
	BLU=$'\033[34m'
	BLD=$'\033[1m'
	RST=$'\033[0m'
else
	RED=
	GRN=
	YLW=
	BLU=
	BLD=
	RST=
fi

# ---------- sanity checks ----------
if [ ! -d "$MOULINETTE_DIR" ]; then
	echo "${RED}Erreur:${RST} dossier moulinette introuvable ($MOULINETTE_DIR)." >&2
	echo "Lance le script depuis la racine du projet, ou exporte AGENTSMITH_ROOT." >&2
	exit 1
fi
mkdir -p "$CACHE_DIR" "$LOG_DIR"

# ---------- arrays résultats ----------
declare -a R_TASK R_CORRECT R_METRICS R_OVERALL R_ITER R_INTOK R_OUTTOK R_TIME

pass_count=0
fail_count=0
error_count=0

# sommes pour les moyennes (uniquement sur les runs qui vont jusqu'au validate)
sum_iter=0
sum_intok=0
sum_outtok=0
n_valid=0
time_list=""

echo "${BLD}Lancement de $N itérations MBPP...${RST}"
echo "Racine : $ROOT"
echo "Logs   : $LOG_DIR"
echo

# ---------- boucle principale ----------
for ((i = 1; i <= N; i++)); do
	echo "${BLD}${BLU}=== Run $i/$N ===${RST}"
	log="$LOG_DIR/run_${i}.log"
	: >"$log"

	# valeurs par défaut (utile si on 'continue' sur erreur)
	R_TASK[i]="?"
	R_CORRECT[i]="-"
	R_METRICS[i]="-"
	R_ITER[i]="-"
	R_INTOK[i]="-"
	R_OUTTOK[i]="-"
	R_TIME[i]="-"

	# 1) DUMP -----------------------------------------------------------
	if ! (cd "$MOULINETTE_DIR" && uv run python3 -m moulinette dump mbpp --output "$TASK_FILE_MOUL") >>"$log" 2>&1; then
		echo "${RED}  ✗ dump a échoué${RST} (voir $log)"
		R_OVERALL[i]="ERROR(dump)"
		((error_count++))
		continue
	fi

	# 2) SOLVE (agent, depuis la racine) --------------------------------
	if ! (cd "$ROOT" && uv run python -m agent_mbpp --task-file "$TASK_FILE_REL" --output "$SOLUTION_FILE_REL") >>"$log" 2>&1; then
		echo "${RED}  ✗ agent a échoué${RST} (voir $log)"
		R_OVERALL[i]="ERROR(agent)"
		((error_count++))
		continue
	fi

	# 3) VALIDATE -------------------------------------------------------
	out="$(cd "$MOULINETTE_DIR" && uv run python3 -m moulinette validate mbpp "$TASK_FILE_MOUL" "$SOLUTION_FILE_MOUL" 2>&1)"
	echo "$out" >>"$log"

	# ---------- parsing ----------
	# (Correctness / Metrics apparaissent 2x -> on prend la dernière occurrence)
	task=$(grep -m1 'Task ID:' <<<"$out" | sed 's/.*Task ID:[[:space:]]*//')
	correct=$(grep 'Correctness:' <<<"$out" | tail -1 | sed 's/.*Correctness:[[:space:]]*//')
	metrics=$(grep 'Metrics:' <<<"$out" | tail -1 | sed 's/.*Metrics:[[:space:]]*//')
	overall=$(grep 'Overall:' <<<"$out" | tail -1 | sed 's/.*Overall:[[:space:]]*//')
	iter=$(grep -m1 'Iterations:' <<<"$out" | sed -E 's/.*Iterations:[[:space:]]*([0-9]+).*/\1/')
	intok=$(grep -m1 'Input tokens:' <<<"$out" | sed -E 's/.*Input tokens:[[:space:]]*([0-9]+).*/\1/')
	outtok=$(grep -m1 'Output tokens:' <<<"$out" | sed -E 's/.*Output tokens:[[:space:]]*([0-9]+).*/\1/')
	time=$(grep -m1 'Time:' <<<"$out" | sed -E 's/.*Time:[[:space:]]*([0-9.]+)s.*/\1/')

	R_TASK[i]="${task:-?}"
	R_CORRECT[i]="${correct:--}"
	R_METRICS[i]="${metrics:--}"
	R_OVERALL[i]="${overall:-?}"
	R_ITER[i]="${iter:-0}"
	R_INTOK[i]="${intok:-0}"
	R_OUTTOK[i]="${outtok:-0}"
	R_TIME[i]="${time:-0}"

	# accumulation pour moyennes
	((sum_iter += R_ITER[i])) || true
	((sum_intok += R_INTOK[i])) || true
	((sum_outtok += R_OUTTOK[i])) || true
	((n_valid++)) || true
	time_list="$time_list ${R_TIME[i]}"

	if [[ "${overall}" == PASSED* ]]; then
		echo "${GRN}  ✓ Task ${R_TASK[i]} → PASSED${RST}  (iter=${R_ITER[i]}, in=${R_INTOK[i]}, out=${R_OUTTOK[i]}, ${R_TIME[i]}s)"
		((pass_count++))
	else
		echo "${RED}  ✗ Task ${R_TASK[i]} → ${overall:-inconnu}${RST}  (correct=${R_CORRECT[i]}, metrics=${R_METRICS[i]})"
		((fail_count++))
		# on garde la task + la solution qui échouent pour debug
		cp -f "$CACHE_DIR/mbpp_task.json" "$LOG_DIR/fail_${i}_task.json" 2>/dev/null || true
		cp -f "$CACHE_DIR/mbpp_solution.json" "$LOG_DIR/fail_${i}_solution.json" 2>/dev/null || true
	fi
done

# ---------- calculs finaux ----------
pass_rate=$(awk -v p="$pass_count" -v n="$N" 'BEGIN{printf "%.0f", (n>0)?100*p/n:0}')

if ((n_valid > 0)); then
	avg_iter=$(awk -v s="$sum_iter" -v n="$n_valid" 'BEGIN{printf "%.1f", s/n}')
	avg_in=$(awk -v s="$sum_intok" -v n="$n_valid" 'BEGIN{printf "%.0f", s/n}')
	avg_out=$(awk -v s="$sum_outtok" -v n="$n_valid" 'BEGIN{printf "%.0f", s/n}')
	sum_time=$(awk -v l="$time_list" 'BEGIN{n=split(l,a," "); s=0; for(k=1;k<=n;k++) s+=a[k]; printf "%.1f", s}')
	avg_time=$(awk -v s="$sum_time" -v n="$n_valid" 'BEGIN{printf "%.1f", s/n}')
else
	avg_iter="-"
	avg_in="-"
	avg_out="-"
	sum_time="-"
	avg_time="-"
fi

# ---------- SUMMARY ----------
echo
echo "${BLD}============================================================${RST}"
echo "${BLD}                  SUMMARY FINAL — MBPP                      ${RST}"
echo "${BLD}============================================================${RST}"
echo

# tableau détaillé
printf "${BLD}%-4s %-6s %-9s %-8s %-6s %-7s %-8s %-7s %s${RST}\n" \
	"Run" "Task" "Correct" "Metrics" "Iter" "InTok" "OutTok" "Time" "Overall"
printf -- "------------------------------------------------------------------------\n"
for ((i = 1; i <= N; i++)); do
	ov="${R_OVERALL[i]}"
	if [[ "$ov" == PASSED* ]]; then
		col="$GRN"
	elif [[ "$ov" == ERROR* ]]; then
		col="$YLW"
	else col="$RED"; fi
	printf "%-4s %-6s %-9s %-8s %-6s %-7s %-8s %-7s ${col}%s${RST}\n" \
		"$i" "${R_TASK[i]}" "${R_CORRECT[i]}" "${R_METRICS[i]}" \
		"${R_ITER[i]}" "${R_INTOK[i]}" "${R_OUTTOK[i]}" "${R_TIME[i]}" "$ov"
done

echo
echo "${BLD}--- Bilan global ---${RST}"
echo "  Itérations demandées : $N"
echo "  ${GRN}PASSED${RST}  : $pass_count   (taux de réussite : ${BLD}${pass_rate}%${RST})"
echo "  ${RED}FAILED${RST}  : $fail_count"
echo "  ${YLW}ERRORS${RST}  : $error_count   (dump/agent plantés avant validate)"
echo
echo "${BLD}--- Moyennes (sur $n_valid run(s) validé(s)) ---${RST}"
echo "  Itérations moy.   : $avg_iter"
echo "  Input tokens moy. : $avg_in"
echo "  Output tokens moy.: $avg_out"
echo "  Temps moy.        : ${avg_time}s   (total : ${sum_time}s)"
echo
echo "  Logs détaillés    : $LOG_DIR/run_*.log"
if ((fail_count > 0)); then
	echo "  Cas en échec      : $LOG_DIR/fail_*_task.json / fail_*_solution.json"
fi
echo "${BLD}============================================================${RST}"

# exit code : 0 si tout PASSED, 1 sinon (pratique en CI)
if ((pass_count == N)); then exit 0; else exit 1; fi
