import datetime

def newtonSolve(f, df, x0, absTol=1E-4, relTol=1E-4, itMax=50, damping=0.70):
    lastX = x0
    nextX = lastX + 10.0 * absTol
    it = 0
    while (abs(lastX - nextX) > absTol or abs(lastX - nextX) > relTol*abs(lastX)):
        it = it + 1
        if it > itMax:
            raise StopIteration('Exceed iteration count')
        newY = f(nextX)
        lastX = nextX
        if (nextX > 10.0 or nextX < -1.0):
            raise StopIteration('Diverging')
        try:
            nextX = lastX - damping * newY / df(nextX)
        except ZeroDivisionError:
            nextX = lastX + absTol
    return nextX
    
def solverF2(rate, cashflowList):
    d0 = cashflowList[0]['date']
    return sum([float(c['cashflow']) / (1 + rate)**((c['date'] - d0).days / 365.0) for c in cashflowList])

def solverDF2(rate, cashflowList):
    d0 = cashflowList[0]['date']
    return sum([-(c['date'] - d0).days/365.0 * float(c['cashflow']) / (1 + rate)**((c['date'] - d0).days / 365.0 + 1.0) for c in cashflowList])

def callSolver2(cashflowList):
    if not cashflowList:
        raise RuntimeError('Empty list')
    r0 = 0
    f = lambda r: solverF2(r, cashflowList)
    df = lambda r: solverDF2(r, cashflowList)

    try:
        r = newtonSolve(f, df, r0)
    except StopIteration:
        raise RuntimeError('Iteration limit exceeded')
        
    return float(r)*100.0
