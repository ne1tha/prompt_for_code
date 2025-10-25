#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

typedef struct player
{
    char name[50];
    int health;
    char card;
}PLAYER;

void fight(PLAYER *str1,PLAYER *str2);

void health(PLAYER *str1);

void fight(PLAYER *str1,PLAYER *str2)
{
    printf("\n\n");
    switch(str1->card)
{
    case 'z':

        switch(str2->card)
        {
        case 'z':

        printf(" %s 与 %s 交换眼神，片刻后两人都蓄势一剑重重的劈在了对方身上，鲜血四溅\n",str1->name,str2->name);
        str1->health += -3;
        str2->health += -3;

        break;
        case 'c':

        printf(" %s 蓄势欲劈，却见 %s 如鬼魅般出手，伸手一刺便洞穿了 %s 的腰腹，制住了 %s 的这一击\n",str1->name,str2->name,str1->name,str1->name);
        str1->health += -1;
        str2->health += 0;

        break;
        case 's':

        printf(" %s 蓄力劈出一剑，却见 %s 移步略闪，单让剑划过了他的衣角，然后反手一剑借势挥出，划开还未收力的 %s 的动脉，霎时间血如泉涌\n",str1->name,str2->name,str1->name);
        str1->health += -3;
        str2->health += 0;

        break;
        case 'd':

        printf(" %s 蓄力劈出一剑，劈中举剑格挡的 %s ，势大力沉的一击虽被抵住，仍将对方打的一个踉跄",str1->name,str2->name);
        str1->health += 0;
        str2->health += -1;

        break;
        case 'y':

        printf(" %s 见势不妙，掏出丹药刚要送入口中，却见 %s 抓住机会，一记大力直劈正中 %s 要害，一大口鲜血伴着刚吃下去的丹药一起从 %s 的口中喷涌而出\n",str2->name,str1->name,str2->name,str2->name);
        str1->health += 0;
        str2->health += -3;

        break;
        }

    break;

    case 'c':
        
        switch(str2->card)
        {
        case 'z':

        printf(" %s 蓄势欲劈，却见 %s 如鬼魅般出手，伸手一刺便洞穿了 %s 的腰腹，制住了 %s 的这一击\n",str2->name,str1->name,str1->name,str1->name);
        str1->health += 0;
        str2->health += -1;

        break;
        case 'c':

        printf(" %s 与 %s 几乎是在同一瞬间出手，一下就洞穿了彼此的躯体，喷射的血液溅了两人一身\n",str1->name,str2->name);
        str1->health += -1;
        str2->health += -1;

        break;
        case 's':

        printf(" %s 屏气凝神，在 %s 身形将要移动的那个瞬间如闪电般的出手，一下把见势欲躲的 %s 贯穿\n",str1->name,str2->name,str2->name);
        str1->health += 0;
        str2->health += -1;

        break;
        case 'd':

        printf(" %s 直手正刺，却被早已识破的 %s 一把格开， %s 抓住了 %s 来不及回防的那个瞬间，舞剑一转，霎时间在 %s 的身上撕裂出巨大的伤口\n",str1->name,str2->name,str2->name,str1->name,str1->name);
        str1->health += -2;
        str2->health += 0;

        break;
        case 'y':

        printf(" %s 面对 %s 刺来的剑不闪不避，掏出一颗丹药服下， %s 的剑刚在 %s 的身上留下一处开口，就被汹涌的药力修复，不消片刻， %s 似乎看起来就更有活力了一些\n",str2->name,str1->name,str1->name,str2->name,str2->name);
        str1->health += 0;
        str2->health += 1;

        break;
        }


    break;

    case 's':

        switch(str2->card)
        {
        case 'z':

        printf(" %s 蓄力劈出一剑，却见 %s 移步略闪，单让剑划过了他的衣角，然后反手一剑借势挥出，划开还未收力的 %s 的动脉，霎时间血如泉涌\n",str2->name,str1->name,str2->name);
        str1->health += -2;
        str2->health += 0;

        break;
        case 'c':

        printf(" %s 屏气凝神，在 %s 身形将要移动的那个瞬间如闪电般的出手，一下把见势欲躲的 %s 贯穿\n",str2->name,str1->name,str1->name);
        str1->health += 0;
        str2->health += -1;

        break;
        case 's':

        printf(" %s 与 %s 互视一眼，各自闪开了一段距离，霎时间，空气中似乎弥漫了一种尴尬的氛围\n",str1->name,str2->name);
        str1->health += 0;
        str2->health += 0;

        break;
        case 'd':

        printf(" %s 举剑欲挡，却见 %s 只是在原地跳了一下，空气中弥漫着一股尴尬的气氛\n",str2->name,str1->name);
        str1->health += 0;
        str2->health += 0;

        break;
        case 'y':

        printf(" %s 只见 %s 微有动作，吓得往后一跳，不料 %s 却是掏出来一颗丹药送入嘴中，整个人身上血痕迅速愈合，变得更加生龙活虎了\n",str1->name,str2->name,str2->name);
        str1->health += 0;
        str2->health += 2;

        break;
        }


    break;

    case 'd':

        switch(str2->card)
        {
        case 'z':

        printf(" %s 蓄力劈出一剑，劈中举剑格挡的 %s ，势大力沉的一击虽被抵住，仍将对方打的一个踉跄",str2->name,str1->name);
        str1->health += 0;
        str2->health += -1;

        break;
        case 'c':

        printf(" %s 直手正刺，却被早已识破的 %s 一把格开， %s 抓住了 %s 来不及回防的那个瞬间，舞剑一转，霎时间在 %s 的身上撕裂出巨大的伤口\n",str2->name,str1->name,str1->name,str2->name,str2->name);
        str1->health += 0;
        str2->health += -2;

        break;
        case 's':

        printf(" %s 举剑欲挡，却见 %s 只是在原地跳了一下，空气中弥漫着一股尴尬的气氛\n",str1->name,str2->name);
        str1->health += 0;
        str2->health += 0;

        break;
        case 'd':

        printf(" %s 与 %s 同时举剑格挡，看来都对敌方抱有谨慎\n",str2->name,str1->name);
        str1->health += 0;
        str2->health += 0;

        break;
        case 'y':

        printf(" %s 举剑格挡，不料 %s 却是掏出来一颗丹药送入嘴中，整个人身上血痕迅速愈合，变得更加生龙活虎了\n",str1->name,str2->name);
        str1->health += 0;
        str2->health += 2;

        break;
        }


    break;

    case 'y':

        switch(str2->card)
        {
        case 'z':

        printf(" %s 见势不妙，掏出丹药刚要送入口中，却见 %s 抓住机会，一记大力直劈正中 %s 要害，一大口鲜血伴着刚吃下去的丹药一起从 %s 的口中喷涌而出\n",str1->name,str2->name,str1->name,str1->name);
        str1->health += -2;
        str2->health += 0;

        break;
        case 'c':

        printf(" %s 面对 %s 刺来的剑不闪不避，掏出一颗丹药服下， %s 的剑刚在 %s 的身上留下一处开口，就被汹涌的药力修复，不消片刻， %s 似乎看起来就更有活力了一些\n",str1->name,str2->name,str2->name,str1->name,str1->name);
        str1->health += 1;
        str2->health += 0;

        break;
        case 's':

        printf(" %s 只见 %s 微有动作，吓得往后一跳，不料 %s 却是掏出来一颗丹药送入嘴中，整个人身上血痕迅速愈合，变得更加生龙活虎了\n",str2->name,str1->name,str1->name);
        str1->health += 2;
        str2->health += 0;

        break;
        case 'd':

        printf(" %s 举剑格挡，不料 %s 却是掏出来一颗丹药送入嘴中，整个人身上血痕迅速愈合，变得更加生龙活虎了\n",str2->name,str1->name);
        str1->health += 2;
        str2->health += 0;

        break;
        case 'y':

        printf(" %s 与 %s 相视一笑，同时掏出来丹药送入口中，两人气势再度回升，陷入了更长的厮杀\n",str1->name,str2->name);
        str1->health += 2;
        str2->health += 2;

        break;
        }


    break;
}
printf("\n");

}

void health(PLAYER *str1)
{
    switch (str1->health)
    {
    case 6:
    case 5:
    printf(" %s 状态良好，双目中斗志熊熊燃烧(%d)\n",str1->name,str1->health);
    break;

    case 4:
    case 3:
    printf(" %s 身上已经在不断渗血了，但明显含有一战之力(%d)\n",str1->name,str1->health);
    break;

    case 2:
    case 1:
    printf(" %s 宛如一个血人，已经奄奄一息了(%d)\n",str1->name,str1->health);
    break;

    default:
    printf(" %s 的身形摇晃几下，终于倒在了地上，一动不动，死的透彻\n",str1->name);
    }
}



int main() {
    PLAYER p1;
    PLAYER p2;
    PLAYER *winner;
    PLAYER *loser;

    printf("欢迎来到战斗牌\n");
    printf("一号玩家请为你的角色起名：");
    scanf(" %s ",p1.name);
    printf("\n二号玩家请为你的角色起名：");
    scanf(" %s ",p2.name);

    printf("\n是否需要说明规则?(y/n)\n");
    char yn;
    fflush(stdin);
    scanf("%c",&yn);
    if(yn == 'y')
    {
        printf("\n每位玩家有六点生命，每个回合依次按规则输入字母与回车打出卡牌，两位玩家都打出卡牌后进行结算并开始下一回合\n");
        printf("输入z打出斩牌，造成两点伤害，但是会被刺与闪克制，值得一提的是，如果双方互斩会一起扣三点血\n");
        printf("输入c打出刺牌，造成一点伤害，如果对方使用了斩可以将其无效，但是会被格挡反制\n");
        printf("输入s打出闪牌，如果对手使用斩牌，可以无效并反击三点\n");
        printf("输入d打出格挡牌，如果对手使用刺牌，可以无效并反击两点，如果对手使用斩，可以减少一点收到的伤害\n");
        printf("输入y打出药牌，可以恢复两点血量，但如果对方使用了斩，会被打断\n\n");
    }
    else if(yn != 'n')
    {
        printf("看不懂，就当你不需要了\n");
    }

    printf("\n那么现在，游戏开始\n");

    HANDLE hStdin = GetStdHandle(STD_INPUT_HANDLE);
    DWORD mode;
    GetConsoleMode(hStdin, &mode);
    mode &= ~ENABLE_ECHO_INPUT;
    SetConsoleMode(hStdin, mode);
    
    p1.health = 6;
    p2.health = 6;

    for(int i = 1;;i++)
    {
        printf("第%d回合\n",i);
        printf("第一位玩家决策：");
        fflush(stdin);
        p1.card = getchar();
        printf("第二位玩家决策：");
        fflush(stdin);
        p2.card = getchar();
        fight(&p1,&p2);
        if(p1.health >= 6)
        {p1.health = 6;}
        if(p2.health >= 6)
        {p2.health = 6;}
        health(&p1);
        health(&p2);
        printf("\n\n请确认战况\n\n");
        fflush(stdin);
        getchar();
        if(p1.health <= 0 ||p2.health <= 0)
        {break;}
    }
    if(p1.health != 0 || p2.health != 0)
    {
        winner = p1.health > 0? &p1 : &p2;
        loser = winner == &p1? &p2 : &p1; 
        printf("战斗结束了，只剩下 %s 仍然站在战场上， %s 割下了 %s 的头，成为了唯一的胜者\n",winner->name,winner->name,loser->name);
    }
    else
    {
        printf("战斗结束了， %s 与 %s 都倒在了地上，等待他们的生命随着血液流尽，除了不久后将吞噬他俩躯体的无情大地外，没有一个胜者",p1.name,p2.name);
    }
    SetConsoleMode(hStdin, mode | ENABLE_ECHO_INPUT);

    return 0;
}


