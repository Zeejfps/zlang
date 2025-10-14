using ParserModule.Visitors;

namespace ParserModule.Nodes;

public abstract class ModuleLevelStatementNode : AstNode
{
    public override void Accept(IAstNodeVisitor visitor)
    {
        Accept(visitor);
    }

    public abstract void Accept(IModuleLevelNodeVisitor visitor);
}