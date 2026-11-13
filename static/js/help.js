// ── Help / User Manual page ───────────────────────────────────
function initHelpPage() {
  document.getElementById("page-help").innerHTML = `
    <div class="page-header">
      <div class="page-title">Ръководство за потребителя</div>
    </div>
    <div style="flex:1;overflow-y:auto">
      <div style="padding:24px 28px;max-width:820px;line-height:1.7;font-size:14px">

        <div class="card" style="margin-bottom:24px;padding:16px 20px">
          <div class="bold" style="margin-bottom:10px;font-size:13px;color:var(--text3)">СЪДЪРЖАНИЕ</div>
          <ol style="margin:0;padding-left:18px;font-size:13px">
            <li><a href="#sec-apts"  style="color:var(--accent)">Апартаменти</a></li>
            <li><a href="#sec-fin"   style="color:var(--accent)">Финанси</a></li>
            <li><a href="#sec-rep"   style="color:var(--accent)">Отчети</a></li>
            <li><a href="#sec-audit" style="color:var(--accent)">Архив и история</a></li>
            <li><a href="#sec-tips"  style="color:var(--accent)">Полезни съвети</a></li>
          </ol>
        </div>

        <div id="sec-apts" style="margin-bottom:32px">
          <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--border)">1. Апартаменти</h2>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Преглед на апартаментите</h3>
          <p>В лявата колона се показва списък с всички апартаменти. При избор вдясно се зарежда подробна информация — собственик, живущи и карти за достъп.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Добавяне на нов апартамент</h3>
          <p>Натиснете <strong>+ Нов апартамент</strong>. Попълнете номера (задължително), етаж, площ, идеални части, брой кучета и бележки.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Редакция и изтриване</h3>
          <p>В детайлния изглед натиснете <strong>✎ Редактирай</strong>. Апартамент <strong>без такси и плащания</strong> се изтрива окончателно. Апартамент, който вече има финансова история, се <strong>архивира</strong>: изчезва от списъка и не получава нови такси, но всичко платено остава в отчетите и наличностите. Архивираните се виждат с отметката <strong>„Покажи архивираните“</strong> и се връщат с <strong>↺ Възстанови</strong>.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Импорт от Excel</h3>
          <p>За първоначално въвеждане натиснете <strong>⬆ Импорт</strong> и поставете редовете, копирани от Excel (или изберете CSV файл). Колони: номер, етаж, кв.м, ид. части, собственик, телефон, е-поща, живее тук (да/не). Съществуващите номера се пропускат.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Проверени данни</h3>
          <p>След като сверите апартамента, собственика и живущите с действителността, натиснете <strong>✓ Потвърди данните</strong>. Записва се датата на проверката, апартаментът получава зелен знак <strong>✓</strong> в списъка отляво.</p>
          <p><strong>Отметката пада автоматично</strong> при всяка следваща промяна на апартамента, собственика или живущите — така знакът винаги означава данни, които наистина са били проверени след последната редакция. Потвърдете отново след промяната.</p>
          <p>Всяко потвърждаване и отменяне се записва в <strong>Архив</strong>.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Собственик</h3>
          <p>Всеки апартамент има един собственик. Натиснете <strong>✎ Редактирай</strong> в секцията „Собственик“ и попълнете трите имена (задължително), ЕГН, телефон и имейл.</p>
          <p><strong>Собственикът се въвежда само веднъж.</strong> С отметката <strong>„Живее в апартамента“</strong> той се записва автоматично и в списъка „Живущи“ и се брои за таксата на живущ. Поправка на името или телефона му се отразява и там. Ако махнете отметката (напр. апартаментът е даден под наем), той остава собственик, но спира да се брои като живущ.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Живущи</h3>
          <p>Натиснете <strong>+ Добави живущ</strong>. Изберете роля: <em>Собственик</em>, <em>Живущ</em> или <em>Наемател</em>. Деактивиран живущ спира да се брои в таксите, но историята се запазва.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Карти за достъп</h3>
          <p>Картите са свързани с апартамента. Добавете произволен брой с <strong>+ Добави карта</strong>. Статусът (<em>Активен / Блокиран / Изгубен</em>) се сменя директно от таблицата.</p>
        </div>

        <div id="sec-fin" style="margin-bottom:32px">
          <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--border)">2. Финанси</h2>

          <p>Изберете месеца от падащото меню. Може да изберете и до три месеца напред. Картите показват: <strong>Приходи</strong>, <strong>Разходи</strong> и <strong>Баланс</strong> за месеца, и наличностите към днес — <strong>В касата</strong> и <strong>В банката</strong> (наличните пари в брой към днес).</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Такси</h3>
          <p>Таксите се изчисляват по формулата:</p>
          <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-family:monospace;font-size:13px;margin:8px 0;border:1px solid var(--border)">
            Такса = фиксирана + (брой живущи × такса/живущ) + (брой кучета × такса/куче)
          </div>
          <p>Натиснете <strong>⟳ Генерирай таксите</strong> за създаване/обновяване на таксите за месеца. Вече платените записи не се презаписват.</p>
          <p><strong>Генерирани по грешка такси:</strong> бутонът <strong>🗑 Изтрий таксите</strong> маха таксите за избрания месец, по които няма плащане. Такси с плащане или приложен аванс не се изтриват — първо махнете плащането. Таксите могат да се генерират отново по всяко време.</p>
          <p><strong>Записване на плащане:</strong> натиснете <strong>✓ Плати</strong> на реда. Сумата, датата и начинът на плащане са попълнени — обикновено остава само Enter. По-малка сума се записва като частично плащане; по-голяма — разликата остава като аванс и покрива следващите месеци. С <strong>🧾</strong> се отваря квитанция (PDF).</p>
          <p>С <strong>✎</strong> се добавя корекция (отстъпка/доплащане) и се поправя грешно отбелязан статус. Отметката <strong>„Само неплатени“</strong> скрива платените, а <strong>⬇ Excel</strong> сваля таблицата като файл.</p>
          <p><strong>Начално салдо:</strong> ако входът вече има пари, въведете ги веднъж от таб <strong>Каса → ⚑ Начално салдо</strong>. От тях се смятат наличностите в касата и в банката.</p>
          <p><strong>Приходи и разходи</strong> влизат в отчета за месеца на <strong>датата</strong> си, независимо кой месец гледате в момента. Записите могат да се редактират с ✎.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Настройки на таксите (⚙ Такси)</h3>
          <p>Задайте фиксирана такса, такса на живущ и добавка за куче. Полето <strong>Валидно от</strong> (формат <code>гггг-мм</code>) определя от кой период важат настройките.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Разходи</h3>
          <p>В таб „Разходи" натиснете <strong>+ Нов разход</strong>. Изберете категория, въведете сума, дата и описание.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Приходи</h3>
          <p>В таб „Приходи" натиснете <strong>+ Нов приход</strong>. Ако са налице категории за приходи, изберете подходяща.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Каса (банка ⇄ каса)</h3>
          <p>Всеки запис — такса, аванс, приход или разход — се отбелязва като <strong>По банка</strong> или <strong>В брой</strong>. Табът <strong>Каса</strong> показва колко пари има в касата на входа към днес.</p>
          <p>Когато изтеглите пари от банковата сметка и ги приберете в касата, натиснете <strong>↓ Теглене от банка</strong>. При обратното движение — <strong>↑ Внасяне в банка</strong>. Въведете сума, дата и бележка.</p>
          <p><strong>Важно:</strong> прехвърлянето не е приход и не е разход — парите са същите, сменя се само мястото им. Затова тези движения <em>не</em> влизат в „Общо приходи", „Общо разходи" и баланса на месеца, а само в касовата наличност. Не ги записвайте като разход по банка + приход в брой — това би удвоило и приходите, и разходите в отчетите.</p>
          <p>Всички движения се виждат и в <strong>Касовия отчет</strong> (таб „Отчети"), с наличност в началото и в края на периода.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Категории (⊞ Категории)</h3>
          <p>Управлявайте категории за разходи и приходи. Превключете между табовете <em>Разходи / Приходи</em>. Изтриването е „меко" — историческите записи се запазват.</p>
        </div>

        <div id="sec-rep" style="margin-bottom:32px">
          <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--border)">3. Отчети</h2>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Месечен отчет</h3>
          <p>Изберете месец и натиснете <strong>⬇ Генерирай PDF</strong>. Съдържа приходи, разходи по категории, баланс, такси по апартаменти и неплатени задължения.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Отчет за период</h3>
          <p>Таб <strong>По период</strong> — изберете начален и краен месец без ограничение. PDF съдържа агрегирани данни за целия период.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Регистър на живущите</h3>
          <p>Списък на всички апартаменти, собственици и активни живущи. Без финансова информация.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Касов отчет</h3>
          <p>Вътрешен отчет само за движенията в брой за избран период от дати — платени в брой такси, аванси, приходи, разходи и прехвърлянията между банка и каса. Завършва с наличността в касата в началото и в края на периода — числото, което трябва да съвпадне с парите, преброени в касата.</p>

          <h3 style="font-size:14px;font-weight:600;margin:16px 0 6px">Изтегляне</h3>
          <p>Всички генерирани файлове се показват в секцията „Генерирани отчети". Натиснете <strong>⬇ Изтегли</strong>.</p>
        </div>

        <div id="sec-audit" style="margin-bottom:32px">
          <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--border)">4. Архив и история</h2>
          <p>Хронологичен лог на всички промени — създаване, редакция, изтриване. Филтрирайте по таблица или търсете по ключова дума. Само за четене.</p>
        </div>

        <div id="sec-tips" style="margin-bottom:32px">
          <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--border)">5. Полезни съвети</h2>
          <div style="display:flex;flex-direction:column;gap:10px">
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Генериране на такси</strong> — Генерирайте след като сте въвели всички живущи. При повторно генериране само незаплатените такси се презаписват.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Деактивиране на живущ</strong> — При напускане деактивирайте (не изтривайте). Историята се запазва, таксата намалява.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Корекции на такси</strong> — Отстъпка: отрицателна стойност (напр. <code>-5.00</code>). Доплащане: положителна.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Резервни копия</strong> — Страницата „Копия“ прави копие на данните с един бутон, сваля го за съхранение на друго място и възстановява старо копие. Пазете от време на време копие извън компютъра.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Изтриване на аванс</strong> — Ако авансът вече е приложен към такси, изтриването му връща тези такси като неплатени. Така касата и отчетите остават верни.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Извлечение по апартамент</strong> — В картата на апартамента, секция „Такси и плащания“, бутонът „Извлечение (PDF)“ дава всички месеци с платено и дължимо — става и за известие до длъжник.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Изход</strong> — Бутонът „⏻ Изход“ долу вляво спира програмата. Повторно стартиране, докато тя работи, само отваря браузъра — не пуска второ копие.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Тема</strong> — Бутонът в долния ляв ъгъл превключва между светла и тъмна тема. Изборът се запомня.
            </div>
            <div style="background:var(--surface2);border-radius:8px;padding:10px 14px;font-size:13px;border:1px solid var(--border)">
              <strong>Клавиши</strong> — Enter записва отворения диалог, Escape го затваря. Клик извън диалога не го затваря, ако вече сте въвели нещо.
            </div>
          </div>
        </div>

        <div style="text-align:center;font-size:12px;color:var(--text4);padding:16px 0">
          ЕС Мениджър v${APP_VERSION}
        </div>

      </div>
    </div>`;
}
