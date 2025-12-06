
from full_analysis import collect_stats_for_cpo, run_cpo_analysis_v2



def run_real_analysis():

    print("Сбор данных...")

    items = collect_stats_for_cpo(days=7)



    print("\nЗапуск CPO v2 анализа...")

    run_cpo_analysis_v2(items)





if __name__ == "__main__":

    run_real_analysis()

